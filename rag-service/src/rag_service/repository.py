import json
from contextlib import contextmanager
from datetime import datetime
from importlib.resources import files
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from rag_service.documents import Chunk, ExtractedPdf
from rag_service.errors import AppError
from rag_service.gemini import EmbeddingBatch, EmbeddingSpace

if TYPE_CHECKING:
    from rag_service.config import Settings

COURSE_CATALOG_LOCK_ID = 7829032


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
            for version, filename in (
                (2, "002_embedding_spaces.sql"),
                (3, "003_document_scopes.sql"),
                (4, "004_gemini_embeddings.sql"),
            ):
                if not connection.execute(
                    "SELECT 1 FROM schema_version WHERE version = %s", (version,),
                ).fetchone():
                    connection.execute(
                        files("rag_service").joinpath("migrations", filename).read_text()
                    )

    def health(self) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') AS vector, "
                "EXISTS(SELECT 1 FROM schema_version WHERE version = 4) AS schema"
            ).fetchone()
            return bool(row["vector"] and row["schema"])

    @contextmanager
    def locked(self, key: str):
        # No mantener transacciones abiertas durante llamadas externas de inferencia.
        # Cerrar la conexión libera el bloqueo, incluso ante un error del proveedor.
        with self.connect() as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
            yield connection

    def find(self, connection, key: str):
        return connection.execute(
            "SELECT d.*, t.nombre AS tipo_documento, "
            "COALESCE(array_agg(dc.course_id ORDER BY dc.course_id) "
            "FILTER (WHERE dc.course_id IS NOT NULL), ARRAY[]::BIGINT[]) AS course_ids "
            "FROM documento d JOIN tipo_documento t USING (id_tipo_documento) "
            "LEFT JOIN documento_curso dc USING (id_documento) "
            "WHERE d.clave = %s GROUP BY d.id_documento, t.nombre", (key,)
        ).fetchone()

    def sync_course_catalog(self, course_ids: list[int]) -> int:
        """Replace active course IDs using an export produced by the trusted Moodle site."""
        if not isinstance(course_ids, list) or any(
            type(course_id) is not int or course_id < 1 for course_id in course_ids
        ):
            raise AppError(
                "invalid_course", "El catálogo contiene un identificador de curso inválido."
            )
        if len(set(course_ids)) != len(course_ids):
            raise AppError("invalid_course", "El catálogo contiene cursos duplicados.")
        with self.connect() as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (COURSE_CATALOG_LOCK_ID,))
            connection.execute("UPDATE curso_moodle SET active = FALSE")
            if course_ids:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO curso_moodle (course_id, active, synced_at) "
                        "VALUES (%s, TRUE, now()) ON CONFLICT (course_id) DO UPDATE SET "
                        "active = TRUE, synced_at = EXCLUDED.synced_at",
                        [(course_id,) for course_id in course_ids],
                    )
        return len(course_ids)

    def validate_course_ids(self, course_ids: tuple[int, ...]) -> None:
        if not course_ids:
            raise AppError("invalid_scope", "Un documento de curso requiere al menos un curso.")
        if any(type(course_id) is not int or course_id < 1 for course_id in course_ids):
            raise AppError("invalid_course", "Los identificadores de curso deben ser positivos.")
        if len(set(course_ids)) != len(course_ids):
            raise AppError("invalid_course", "Los identificadores de curso están duplicados.")
        with self.connect() as connection:
            self._validate_active_course_ids(connection, course_ids)

    @staticmethod
    def _validate_active_course_ids(connection, course_ids: tuple[int, ...]) -> None:
        active = connection.execute(
            "SELECT course_id FROM curso_moodle WHERE active AND course_id = ANY(%s)",
            (list(course_ids),),
        ).fetchall()
        if {row["course_id"] for row in active} != set(course_ids):
            raise AppError(
                "invalid_course", "El catálogo Moodle no contiene todos los cursos indicados."
            )

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
        scope: str,
        course_ids: tuple[int, ...],
        batches: list[EmbeddingBatch] | None = None,
    ) -> dict:
        batches = batches or [EmbeddingBatch(EmbeddingSpace(
            "gemini", self.settings.gemini_embedding_model, "v1beta",
            self.settings.gemini_embedding_dimensions,
        ), vectors)]
        primary = batches[0].space
        vectors = batches[0].vectors
        if any(len(batch.vectors) != len(chunks) for batch in batches):
            raise AppError("invalid_embedding", "El lote de embeddings está incompleto.")
        with connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (COURSE_CATALOG_LOCK_ID,))
            if scope == "course":
                self._validate_active_course_ids(connection, course_ids)
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
                    revision_embedding, alcance
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'INDEXADO',%s,%s,%s)
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
                    alcance = EXCLUDED.alcance,
                    chunk_size_chars = EXCLUDED.chunk_size_chars,
                    chunk_overlap_chars = EXCLUDED.chunk_overlap_chars,
                    version = documento.version + 1, fecha_actualizacion = now()
                RETURNING id_documento, clave, titulo, version, estado, alcance""",
                (
                    key, category["id_tipo_documento"], title, pdf.filename, pdf.path, pdf.sha256,
                    pdf.total_pages, Jsonb(list(pdf.skipped_pages)), primary.model,
                    primary.dimensions, self.settings.chunk_size_chars,
                    self.settings.chunk_overlap_chars, primary.provider, primary.revision, scope,
                ),
            ).fetchone()
            document_id = row["id_documento"]
            connection.execute(
                "DELETE FROM documento_curso WHERE id_documento = %s", (document_id,)
            )
            if scope == "course":
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO documento_curso (id_documento, course_id) VALUES (%s, %s)",
                        [(document_id, course_id) for course_id in course_ids],
                    )
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
                copia_local=False,
                course_ids=list(course_ids),
            )

    def list_documents(self):
        with self.connect() as connection:
            return connection.execute(
                """SELECT d.id_documento, d.clave, d.titulo, d.version, d.estado, d.alcance,
                d.modelo_embedding, d.dimension_embedding,
                d.proveedor_embedding, d.revision_embedding,
                count(DISTINCT f.id_fragmento) AS total_fragmentos,
                COALESCE(array_agg(DISTINCT dc.course_id) FILTER (WHERE dc.course_id IS NOT NULL),
                    ARRAY[]::BIGINT[]) AS course_ids
                FROM documento d LEFT JOIN fragmento f USING (id_documento)
                LEFT JOIN documento_curso dc USING (id_documento)
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

    def prepare_embedding_index(self, provider):
        """Rebuild embeddings from stored fragments without holding DB locks during inference."""
        for document in self.list_documents():
            with self.locked(document["clave"]) as connection:
                fragments = connection.execute(
                    "SELECT id_fragmento, contenido FROM fragmento "
                    "WHERE id_documento = %s ORDER BY posicion", (document["id_documento"],),
                ).fetchall()
                if not fragments:  # Puede haberse eliminado mientras esperaba el bloqueo.
                    continue
                target = getattr(provider, "space", None)
                fragment_ids = [fragment["id_fragmento"] for fragment in fragments]
                if target is not None:
                    indexed = connection.execute(
                        """SELECT count(*) AS n FROM fragmento_embedding fe
                        JOIN espacio_embedding e USING (id_espacio)
                        WHERE fe.id_fragmento = ANY(%s) AND e.proveedor = %s
                            AND e.modelo = %s AND e.revision = %s AND e.dimensiones = %s""",
                        (fragment_ids, target.provider, target.model,
                         target.revision, target.dimensions),
                    ).fetchone()["n"]
                    document_current = all((
                        document["proveedor_embedding"] == target.provider,
                        document["modelo_embedding"] == target.model,
                        document["revision_embedding"] == target.revision,
                        document["dimension_embedding"] == target.dimensions,
                    ))
                    if indexed == len(fragments) and document_current:
                        continue
                batch = provider.embed_many([fragment["contenido"] for fragment in fragments])
                with connection.transaction():
                    self.save_space(connection, fragment_ids, batch)
                    connection.execute(
                        """UPDATE documento SET proveedor_embedding = %s, modelo_embedding = %s,
                        revision_embedding = %s, dimension_embedding = %s,
                        fecha_actualizacion = now() WHERE id_documento = %s""",
                        (batch.space.provider, batch.space.model, batch.space.revision,
                         batch.space.dimensions, document["id_documento"]),
                    )
        return self.index_status()

    def prepare_local_index(self, provider):
        """Deprecated compatibility wrapper; use prepare_embedding_index."""
        return self.prepare_embedding_index(provider)

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

    def retrieve(self, space, vector, *, course_ids: tuple[int, ...] = (), limit=4):
        if any(type(course_id) is not int or course_id < 1 for course_id in course_ids):
            raise AppError("invalid_scope", "El alcance de cursos no es válido.")
        access_filter = """(
            d.alcance = 'institutional'
            OR (d.alcance = 'course' AND EXISTS (
                SELECT 1 FROM documento_curso dc
                JOIN curso_moodle mc USING (course_id)
                WHERE dc.id_documento = d.id_documento AND mc.active
                    AND dc.course_id = ANY(%s)
            ))
        )"""
        with self.connect() as connection, connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            embedding_space = connection.execute(
                "SELECT id_espacio FROM espacio_embedding WHERE proveedor = %s AND modelo = %s "
                "AND revision = %s AND dimensiones = %s",
                (space.provider, space.model, space.revision, space.dimensions),
            ).fetchone()
            total = connection.execute(
                f"SELECT count(*) AS n FROM fragmento f JOIN documento d USING (id_documento) "
                f"WHERE d.vigente AND {access_filter}",
                (list(course_ids),),
            ).fetchone()["n"]
            if not total:
                return []
            if embedding_space is None:
                raise AppError(
                    "index_incomplete", "Prepare el índice Gemini con rag prepare-gemini-index.",
                )
            space_id = embedding_space["id_espacio"]
            coverage = connection.execute(
                "SELECT count(*) AS n FROM fragmento_embedding fe "
                "JOIN fragmento f USING (id_fragmento) JOIN documento d USING (id_documento) "
                f"WHERE fe.id_espacio = %s AND d.vigente AND {access_filter}",
                (space_id, list(course_ids)),
            ).fetchone()["n"]
            if coverage != total:
                raise AppError(
                    "index_incomplete", "El índice Gemini no cubre los documentos actuales.",
                )
            return connection.execute(
                f"""SELECT f.id_fragmento, f.id_documento, f.contenido, f.pagina_inicio,
                f.pagina_fin, d.clave, d.titulo, d.nombre_archivo, d.version,
                d.alcance, t.nombre AS tipo_documento
                FROM fragmento_embedding fe JOIN fragmento f USING (id_fragmento)
                JOIN documento d USING (id_documento)
                JOIN tipo_documento t USING (id_tipo_documento)
                WHERE fe.id_espacio = %s AND d.vigente AND {access_filter}
                    AND (fe.embedding <=> %s::vector) IS NOT NULL
                ORDER BY fe.embedding <=> %s::vector, f.id_fragmento LIMIT %s""",
                (space_id, list(course_ids), json.dumps(vector), json.dumps(vector), limit),
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
