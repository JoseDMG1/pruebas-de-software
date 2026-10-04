import json
from contextlib import contextmanager
from datetime import datetime
from importlib.resources import files
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rag_service.constants import EMBEDDING_DIMENSIONS
from rag_service.documents import Chunk, ExtractedPdf
from rag_service.errors import AppError
from rag_service.local_embeddings import EmbeddingBatch, EmbeddingSpace

if TYPE_CHECKING:
    from rag_service.config import Settings


class Repository:
    def __init__(self, settings: "Settings"):
        self.settings = settings

    def connect(self):
        return psycopg.connect(
            self.settings.database_url,
            connect_timeout=self.settings.db_connect_timeout,
            autocommit=True,
            row_factory=dict_row,
        )

    def initialize(self):
        migration = files("rag_service").joinpath("migrations/001_initial.sql").read_text()
        with self.connect() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(7829031)")
            connection.execute(migration)
            if not connection.execute(
                "SELECT 1 FROM schema_version WHERE version = 2"
            ).fetchone():
                connection.execute(files("rag_service").joinpath(
                    "migrations/002_embedding_spaces.sql",
                ).read_text())

    def health(self) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') AS vector, "
                "EXISTS(SELECT 1 FROM schema_version WHERE version = 2) AS schema"
            ).fetchone()
            return bool(row["vector"] and row["schema"])

    @contextmanager
    def locked(self, key: str):
        # Bloqueo de sesión: las llamadas a Bedrock no mantienen una transacción abierta.
        # Cerrar la conexión libera el bloqueo, incluso ante un error del proveedor.
        with self.connect() as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
            yield connection

    def find(self, connection, key: str):
        return connection.execute(
            "SELECT d.*, t.nombre AS tipo_documento FROM documento d "
            "JOIN tipo_documento t USING (id_tipo_documento) WHERE clave = %s", (key,)
        ).fetchone()

    def save(
        self,
        connection,
        key: str,
        title: str,
        kind: str,
        pdf: ExtractedPdf,
        chunks: list[Chunk],
        vectors: list[list[float]],
        started_at: datetime,
        *,
        batches: list[EmbeddingBatch] | None = None,
    ) -> dict:
        batches = batches or [EmbeddingBatch(EmbeddingSpace(
            "bedrock", self.settings.bedrock_model_id, "", EMBEDDING_DIMENSIONS,
        ), vectors)]
        primary = batches[0].space
        vectors = batches[0].vectors
        if any(len(batch.vectors) != len(chunks) for batch in batches):
            raise AppError("invalid_embedding", "El lote de embeddings está incompleto.")
        with connection.transaction():
            category = connection.execute(
                "SELECT id_tipo_documento FROM tipo_documento WHERE nombre = %s", (kind,)
            ).fetchone()
            if category is None:
                raise AppError("invalid_kind", "El tipo de documento no es válido.")
            row = connection.execute(
                """INSERT INTO documento (
                    clave, id_tipo_documento, titulo, nombre_archivo, ruta_archivo, sha256,
                    total_paginas, paginas_sin_texto, modelo_embedding, dimension_embedding,
                    chunk_size_chars, chunk_overlap_chars, estado, proveedor_embedding,
                    revision_embedding
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'INDEXADO',%s,%s)
                ON CONFLICT (clave) DO UPDATE SET
                    id_tipo_documento = EXCLUDED.id_tipo_documento,
                    titulo = EXCLUDED.titulo, nombre_archivo = EXCLUDED.nombre_archivo,
                    ruta_archivo = EXCLUDED.ruta_archivo, sha256 = EXCLUDED.sha256,
                    total_paginas = EXCLUDED.total_paginas,
                    paginas_sin_texto = EXCLUDED.paginas_sin_texto,
                    modelo_embedding = EXCLUDED.modelo_embedding,
                    dimension_embedding = EXCLUDED.dimension_embedding,
                    proveedor_embedding = EXCLUDED.proveedor_embedding,
                    revision_embedding = EXCLUDED.revision_embedding,
                    chunk_size_chars = EXCLUDED.chunk_size_chars,
                    chunk_overlap_chars = EXCLUDED.chunk_overlap_chars,
                    version = documento.version + 1, fecha_actualizacion = now()
                RETURNING id_documento, clave, titulo, version, estado""",
                (
                    key, category["id_tipo_documento"], title, pdf.filename, pdf.path, pdf.sha256,
                    pdf.total_pages, Jsonb(list(pdf.skipped_pages)), primary.model,
                    primary.dimensions, self.settings.chunk_size_chars,
                    self.settings.chunk_overlap_chars, primary.provider, primary.revision,
                ),
            ).fetchone()
            document_id = row["id_documento"]
            connection.execute("DELETE FROM fragmento WHERE id_documento = %s", (document_id,))
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO fragmento
                    (id_documento, contenido, posicion, pagina_inicio, pagina_fin,
                     embedding, metadata)
                    VALUES (%s,%s,%s,%s,%s,%s::vector,%s)""",
                    [
                        (
                            document_id, chunk.text, chunk.position, chunk.page_start,
                            chunk.page_end,
                            json.dumps(vector) if primary.provider == "bedrock" else None,
                            Jsonb({"sha256": pdf.sha256}),
                        )
                        for chunk, vector in zip(chunks, vectors, strict=True)
                    ],
                )
            fragment_ids = [item["id_fragmento"] for item in connection.execute(
                "SELECT id_fragmento FROM fragmento WHERE id_documento = %s ORDER BY posicion",
                (document_id,),
            ).fetchall()]
            for batch in batches:
                self.save_space(connection, fragment_ids, batch)
            connection.execute(
                """INSERT INTO proceso_indexacion
                (id_documento, estado, fecha_inicio, total_fragmentos, modelo_embedding,
                 dimension_embedding, proveedor_embedding, revision_embedding)
                VALUES (%s,'COMPLETADO',%s,%s,%s,%s,%s,%s)""",
                (
                    document_id, started_at, len(chunks), primary.model,
                    primary.dimensions, primary.provider, primary.revision,
                ),
            )
            return dict(
                row, total_fragmentos=len(chunks), paginas_sin_texto=list(pdf.skipped_pages),
                proveedor_embedding=primary.provider, modelo_embedding=primary.model,
                revision_embedding=primary.revision, dimension_embedding=primary.dimensions,
                copia_local=any(batch.space.provider == "ollama" for batch in batches),
            )

    def list_documents(self):
        with self.connect() as connection:
            return connection.execute(
                """SELECT d.id_documento, d.clave, d.titulo, d.version, d.estado,
                d.modelo_embedding, d.dimension_embedding,
                d.proveedor_embedding, d.revision_embedding,
                count(f.id_fragmento) AS total_fragmentos
                FROM documento d LEFT JOIN fragmento f USING (id_documento)
                GROUP BY d.id_documento ORDER BY d.id_documento"""
            ).fetchall()

    def delete(self, key: str) -> bool:
        with self.locked(key) as connection, connection.transaction():
            return connection.execute(
                "DELETE FROM documento WHERE clave = %s RETURNING id_documento", (key,)
            ).fetchone() is not None

    def save_space(self, connection, fragment_ids, batch):
        space = batch.space
        row = connection.execute(
            """INSERT INTO espacio_embedding (proveedor, modelo, revision, dimensiones)
            VALUES (%s,%s,%s,%s) ON CONFLICT (proveedor, modelo, revision, dimensiones)
            DO UPDATE SET modelo = EXCLUDED.modelo RETURNING id_espacio""",
            (space.provider, space.model, space.revision, space.dimensions),
        ).fetchone()
        with connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO fragmento_embedding
                (id_fragmento, id_espacio, dimensiones, embedding) VALUES (%s,%s,%s,%s::vector)
                ON CONFLICT (id_fragmento, id_espacio)
                DO UPDATE SET embedding = EXCLUDED.embedding""",
                [(fragment_id, row["id_espacio"], space.dimensions, json.dumps(vector))
                 for fragment_id, vector in zip(fragment_ids, batch.vectors, strict=True)],
            )

    def prepare_local_index(self, provider):
        # Una transacción corta por documento; no mantiene transacciones durante inferencia.
        for document in self.list_documents():
            with self.locked(document["clave"]) as connection:
                fragments = connection.execute(
                    "SELECT id_fragmento, contenido FROM fragmento "
                    "WHERE id_documento = %s ORDER BY posicion", (document["id_documento"],),
                ).fetchall()
                if not fragments:  # Puede haberse eliminado mientras esperaba el bloqueo.
                    continue
                batch = provider.embed_many([fragment["contenido"] for fragment in fragments])
                with connection.transaction():
                    self.save_space(connection, [f["id_fragmento"] for f in fragments], batch)
        return self.index_status()

    def index_status(self):
        with self.connect() as connection:
            return connection.execute(
                """SELECT e.proveedor, e.modelo, e.revision, e.dimensiones,
                count(fe.id_fragmento) AS fragmentos_indexados,
                (SELECT count(*) FROM fragmento) AS fragmentos_actuales,
                count(fe.id_fragmento) > 0 AND count(fe.id_fragmento) =
                    (SELECT count(*) FROM fragmento) AS listo
                FROM espacio_embedding e LEFT JOIN fragmento_embedding fe USING (id_espacio)
                GROUP BY e.id_espacio ORDER BY e.id_espacio"""
            ).fetchall()

    def retrieve(self, space, vector, *, limit=4):
        with self.connect() as connection, connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            embedding_space = connection.execute(
                "SELECT id_espacio FROM espacio_embedding WHERE proveedor = %s AND modelo = %s "
                "AND revision = %s AND dimensiones = %s",
                (space.provider, space.model, space.revision, space.dimensions),
            ).fetchone()
            total = connection.execute(
                "SELECT count(*) AS n FROM fragmento JOIN documento USING (id_documento) "
                "WHERE vigente"
            ).fetchone()["n"]
            if not total:
                return []
            if embedding_space is None:
                raise AppError(
                    "index_incomplete", "Prepare el índice local con rag prepare-local-index.",
                )
            space_id = embedding_space["id_espacio"]
            coverage = connection.execute(
                "SELECT count(*) AS n FROM fragmento_embedding fe "
                "JOIN fragmento f USING (id_fragmento) JOIN documento d USING (id_documento) "
                "WHERE fe.id_espacio = %s AND d.vigente", (space_id,),
            ).fetchone()["n"]
            if coverage != total:
                raise AppError(
                    "index_incomplete", "El índice local no cubre los documentos actuales.",
                )
            return connection.execute(
                """SELECT f.id_fragmento, f.id_documento, f.contenido, f.pagina_inicio,
                f.pagina_fin, d.clave, d.titulo, d.nombre_archivo, d.version
                FROM fragmento_embedding fe JOIN fragmento f USING (id_fragmento)
                JOIN documento d USING (id_documento)
                WHERE fe.id_espacio = %s AND d.vigente
                    AND (fe.embedding <=> %s::vector) IS NOT NULL
                ORDER BY fe.embedding <=> %s::vector, f.id_fragmento LIMIT %s""",
                (space_id, json.dumps(vector), json.dumps(vector), limit),
            ).fetchall()

    def sources_current(self, fragments):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT f.id_fragmento, d.version FROM fragmento f "
                "JOIN documento d USING (id_documento) WHERE d.vigente "
                "AND f.id_fragmento = ANY(%s)",
                ([row["id_fragmento"] for row in fragments],),
            ).fetchall()
            actual = {row["id_fragmento"]: row["version"] for row in rows}
            return all(actual.get(row["id_fragmento"]) == row["version"] for row in fragments)
