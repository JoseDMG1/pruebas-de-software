import os
import uuid

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic_settings")
pytest.importorskip("pypdf")
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

import psycopg
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from conftest import pdf_bytes
from rag_service.api import create_app
from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.ingestion import ingest
from rag_service.repository import Repository

pytestmark = pytest.mark.integration


class FakeProvider:
    def embed(self, text):
        return [1.0] + [0.0] * 1023


@pytest.fixture
def repository(request):
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL no definido")
    schema = "test_" + uuid.uuid4().hex
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        connection.execute(f'CREATE SCHEMA "{schema}"')
    settings = Settings(
        _env_file=None,
        ollama_embedding_model=None,
        database_url=make_conninfo(
            database_url,
            options=f"-csearch_path={schema},public",
        ),
    )
    repository = Repository(settings)
    try:
        if getattr(request, "param", None) == "legacy":
            from importlib.resources import files

            with repository.connect() as connection:
                connection.execute(
                    files("rag_service")
                    .joinpath(
                        "migrations/001_initial.sql",
                    )
                    .read_text()
                )
        else:
            repository.initialize()
            repository.initialize()  # Migración repetible.
        yield repository
    finally:
        with psycopg.connect(database_url, autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_pdf_ingestion_update_and_delete(repository, sample_pdf):
    first = ingest(
        sample_pdf, repository.settings, repository, FakeProvider(),
        key="reglamento", scope="institutional",
    )
    with repository.connect() as connection:
        original = connection.execute(
            "SELECT contenido, vector_dims(embedding) AS dims, pagina_inicio FROM fragmento "
            "ORDER BY posicion"
        ).fetchall()
    assert len(original) == first["total_fragmentos"] == 2
    assert all(row["dims"] == 1024 for row in original)
    assert [row["pagina_inicio"] for row in original] == [1, 2]
    sample_pdf.write_bytes(pdf_bytes(["Updated regulations."]))
    second = ingest(
        sample_pdf, repository.settings, repository, FakeProvider(),
        key="reglamento", scope="institutional",
    )
    assert first["id_documento"] == second["id_documento"] and second["version"] == 2
    assert repository.list_documents()[0]["total_fragmentos"] == 1
    assert repository.list_documents()[0]["alcance"] == "institutional"
    assert repository.list_documents()[0]["course_ids"] == []
    assert repository.delete("reglamento")
    with repository.connect() as connection:
        assert connection.execute("SELECT count(*) AS n FROM fragmento").fetchone()["n"] == 0
        count = connection.execute("SELECT count(*) AS n FROM proceso_indexacion").fetchone()["n"]
        assert count == 0
    assert not repository.delete("reglamento")


def test_course_document_requires_an_active_moodle_course(repository, sample_pdf):
    repository.sync_course_catalog([18, 19])
    result = ingest(
        sample_pdf, repository.settings, repository, FakeProvider(), key="course-18",
        scope="course", course_ids=(18,),
    )

    assert result["alcance"] == "course" and result["course_ids"] == [18]

    sample_pdf.write_bytes(pdf_bytes(["Updated course material."]))
    updated = ingest(
        sample_pdf, repository.settings, repository, FakeProvider(), key="course-18",
        scope="course", course_ids=(19,),
    )
    assert updated["version"] == 2
    from rag_service.local_embeddings import OllamaEmbeddingProvider
    from test_local_embeddings import OllamaAPI

    repository.prepare_local_index(
        OllamaEmbeddingProvider(repository.settings, OllamaAPI(dimensions=3))
    )
    reindexed = repository.list_documents()[0]
    assert reindexed["alcance"] == "course" and reindexed["course_ids"] == [19]
    repository.initialize()
    document = repository.list_documents()[0]
    assert document["alcance"] == "course" and document["course_ids"] == [19]

    repository.sync_course_catalog([])
    with pytest.raises(AppError) as error:
        ingest(
            sample_pdf, repository.settings, repository, FakeProvider(), key="course-19",
            scope="course", course_ids=(19,),
        )
    assert error.value.code == "invalid_course"


def test_moodle_course_catalog_import_replaces_active_course_ids(
    repository, tmp_path, monkeypatch, capsys
):
    import json

    from rag_service.cli import main

    catalog = tmp_path / "courses.json"
    catalog.write_text(json.dumps({"course_ids": [18, 19]}))
    monkeypatch.setattr("rag_service.cli.Settings", lambda: repository.settings)

    assert main(["sync-courses", str(catalog)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first == {"status": "ok", "courses_synced": 2}

    catalog.write_text(json.dumps({"course_ids": [19]}))
    assert main(["sync-courses", str(catalog)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second == {"status": "ok", "courses_synced": 1}

    with pytest.raises(AppError) as error:
        repository.validate_course_ids((18,))
    assert error.value.code == "invalid_course"


def test_retrieval_filters_course_documents_before_returning_fragments(repository, tmp_path):
    from rag_service.local_embeddings import EmbeddingSpace

    repository.sync_course_catalog([18, 19])
    documents = [
        ("restricted-19", "COURSE NINETEEN SECRET", "course", (19,)),
        ("allowed-18", "COURSE EIGHTEEN MATERIAL", "course", (18,)),
        ("shared", "INSTITUTIONAL COMMON MATERIAL", "institutional", ()),
    ]
    for key, text, scope, course_ids in documents:
        path = tmp_path / f"{key}.pdf"
        path.write_bytes(pdf_bytes([text]))
        ingest(
            path, repository.settings, repository, FakeProvider(), key=key, scope=scope,
            course_ids=course_ids,
        )

    rows = repository.retrieve(
        EmbeddingSpace("bedrock", repository.settings.bedrock_model_id, "", 1024),
        [1.0] + [0.0] * 1023,
        course_ids=(18,),
        limit=10,
    )

    contents = [row["contenido"] for row in rows]
    assert any("COURSE EIGHTEEN MATERIAL" in text for text in contents)
    assert any("INSTITUTIONAL COMMON MATERIAL" in text for text in contents)
    assert all("COURSE NINETEEN SECRET" not in text for text in contents)
    assert {row["alcance"] for row in rows} == {"course", "institutional"}
    assert all(row["tipo_documento"] == "OTRO" for row in rows)

    common_only = repository.retrieve(
        EmbeddingSpace("bedrock", repository.settings.bedrock_model_id, "", 1024),
        [1.0] + [0.0] * 1023,
        limit=10,
    )
    common_contents = [row["contenido"] for row in common_only]
    assert any("INSTITUTIONAL COMMON MATERIAL" in text for text in common_contents)
    assert all("COURSE EIGHTEEN MATERIAL" not in text for text in common_contents)
    assert all("COURSE NINETEEN SECRET" not in text for text in common_contents)


def test_protected_api_filters_course_documents_before_prompt_and_sources(repository, tmp_path):
    import json

    from fastapi.testclient import TestClient

    from rag_service.api import create_app
    from rag_service.config import Settings
    from rag_service.local_embeddings import EmbeddingBatch, EmbeddingSpace
    from rag_service.query import GenerationOutput, QueryService
    from moodle_auth_support import signed_moodle_headers

    repository.sync_course_catalog([18, 19])
    documents = [
        ("restricted-19", "COURSE NINETEEN SECRET", "course", (19,)),
        ("allowed-18", "COURSE EIGHTEEN MATERIAL", "course", (18,)),
        ("shared", "INSTITUTIONAL COMMON MATERIAL", "institutional", ()),
    ]
    for key, text, scope, course_ids in documents:
        path = tmp_path / f"{key}.pdf"
        path.write_bytes(pdf_bytes([text]))
        ingest(
            path, repository.settings, repository, FakeProvider(), key=key, scope=scope,
            course_ids=course_ids,
        )

    class QueryEmbeddings:
        def embed_query(self, question):
            space = EmbeddingSpace(
                "bedrock", repository.settings.bedrock_model_id, "", 1024,
            )
            return EmbeddingBatch(space, [[1.0] + [0.0] * 1023])

    class InspectingChat:
        def __init__(self):
            self.prompt_fragments = []

        def generate(
            self, question, fragments, *, academic_context=None, conversation_context=None
        ):
            self.prompt_fragments = [row["contenido"] for row in fragments]
            return GenerationOutput(
                answer="Contenido disponible. [1]", insufficient_context=False, source_ids=[1],
            )

    secret = "test-shared-secret-that-is-long-enough"
    chat = InspectingChat()
    service = QueryService(repository.settings, repository, QueryEmbeddings(), chat)
    settings = Settings(
        _env_file=None, database_url=repository.settings.database_url,
        moodle_service_secret=secret,
    )
    client = TestClient(create_app(settings, repository, service))
    body = json.dumps(
        {"query": "¿Qué material del curso puedo consultar?", "academic_context": {}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    headers = signed_moodle_headers(secret, body, courses=[18])

    response = client.post("/api/v1/chat/query", content=body, headers=headers)

    assert response.status_code == 200
    assert any("COURSE EIGHTEEN MATERIAL" in text for text in chat.prompt_fragments)
    assert any("INSTITUTIONAL COMMON MATERIAL" in text for text in chat.prompt_fragments)
    assert all("COURSE NINETEEN SECRET" not in text for text in chat.prompt_fragments)
    assert all(
        "COURSE NINETEEN SECRET" not in source["excerpt"]
        for source in response.json()["sources"]
    )

    chat.prompt_fragments = []
    common_only_headers = signed_moodle_headers(secret, body, courses=[])
    common_only_response = client.post(
        "/api/v1/chat/query", content=body, headers=common_only_headers,
    )
    assert common_only_response.status_code == 200
    assert any("INSTITUTIONAL COMMON MATERIAL" in text for text in chat.prompt_fragments)
    assert all("COURSE EIGHTEEN MATERIAL" not in text for text in chat.prompt_fragments)
    assert all("COURSE NINETEEN SECRET" not in text for text in chat.prompt_fragments)


def test_database_failure_rolls_back_existing_fragments(repository, sample_pdf):
    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    with repository.connect() as connection:
        connection.execute(
            "ALTER TABLE fragmento ADD CONSTRAINT test_reject CHECK (length(contenido) > 10)"
        )
    sample_pdf.write_bytes(pdf_bytes(["short"]))
    with pytest.raises(psycopg.errors.CheckViolation):
        ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    documents = repository.list_documents()
    assert documents[0]["version"] == 1 and documents[0]["total_fragmentos"] == 2
    with repository.connect() as connection:
        count = connection.execute("SELECT count(*) AS n FROM proceso_indexacion").fetchone()["n"]
        assert count == 1


def test_concurrent_ingestions_do_not_duplicate_versions(repository, sample_pdf):
    from concurrent.futures import ThreadPoolExecutor

    def run():
        return ingest(
            sample_pdf, repository.settings, repository, FakeProvider(),
            key="shared", scope="institutional",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: run(), range(2)))
    assert sorted(result["status"] for result in results) == ["indexed", "unchanged"]
    documents = repository.list_documents()
    assert len(documents) == 1 and documents[0]["version"] == 1


def test_health_checks_real_database_and_reports_missing_schema(repository):
    with TestClient(create_app(repository.settings, repository)) as client:
        response = client.get("/health")
    assert response.status_code == 200 and response.json()["database"] == "ok"
    missing_schema = "missing_" + uuid.uuid4().hex
    settings = repository.settings.model_copy(
        update={
            "database_url": make_conninfo(
                repository.settings.database_url,
                options=f"-csearch_path={missing_schema}",
            ),
        }
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/health")
    assert response.status_code == 503 and response.json()["database"] == "unavailable"


def test_local_copy_preserves_cloud_vectors_and_tracks_updates_and_deletes(repository, sample_pdf):
    from rag_service.local_embeddings import EmbeddingRouter, OllamaEmbeddingProvider
    from test_local_embeddings import Bedrock, OllamaAPI

    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    provider = OllamaEmbeddingProvider(repository.settings, OllamaAPI(dimensions=3))
    status = repository.prepare_local_index(provider)
    assert {space["proveedor"] for space in status} == {"bedrock", "ollama"}
    assert all(space["listo"] for space in status)
    with repository.connect() as connection:
        assert (
            connection.execute(
                "SELECT min(vector_dims(embedding)) AS dims FROM fragmento"
            ).fetchone()["dims"]
            == 1024
        )
    settings = repository.settings.model_copy(update={"embedding_backend": "ollama"})
    sample_pdf.write_bytes(pdf_bytes(["Updated local regulations."]))
    router = EmbeddingRouter(settings, Bedrock(), provider)
    result = ingest(sample_pdf, settings, repository, router, scope="institutional")
    assert result["dimension_embedding"] == 3 and result["proveedor_embedding"] == "ollama"
    status = repository.index_status()
    assert next(space for space in status if space["proveedor"] == "ollama")["listo"]
    assert not next(space for space in status if space["proveedor"] == "bedrock")["listo"]
    with repository.connect() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM fragmento WHERE embedding IS NOT NULL"
            ).fetchone()["n"]
            == 0
        )
    assert repository.delete(sample_pdf.name)
    assert all(
        not space["listo"] and space["fragmentos_indexados"] == 0
        for space in repository.index_status()
    )


def test_bad_local_copy_does_not_destroy_existing_index(repository, sample_pdf):
    from rag_service.local_embeddings import EmbeddingBatch, EmbeddingSpace

    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    with repository.connect() as connection:
        fragments = connection.execute(
            "SELECT id_fragmento FROM fragmento ORDER BY posicion"
        ).fetchall()
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            repository.save_space(
                connection,
                [row["id_fragmento"] for row in fragments],
                EmbeddingBatch(
                    EmbeddingSpace("ollama", "bad", "a", 3), [[1.0, 2.0]] * len(fragments)
                ),
            )
    assert len(repository.index_status()) == 1
    assert repository.index_status()[0]["listo"]


@pytest.mark.parametrize("repository", ["legacy"], indirect=True)
def test_migration_preserves_legacy_vectors_and_is_repeatable(repository):
    import json

    from rag_service.local_embeddings import EmbeddingSpace

    with repository.connect() as connection:
        document = connection.execute(
            """INSERT INTO documento (clave, id_tipo_documento, titulo, nombre_archivo,
            ruta_archivo, sha256, total_paginas, modelo_embedding, dimension_embedding,
            chunk_size_chars, chunk_overlap_chars, estado)
            VALUES ('old', (SELECT id_tipo_documento FROM tipo_documento WHERE nombre='OTRO'),
            'Old', 'old.pdf', '/old.pdf', %s, 1, %s, 1024, 2000, 200, 'INDEXADO')
            RETURNING id_documento""",
            ("a" * 64, repository.settings.bedrock_model_id),
        ).fetchone()
        connection.execute(
            """INSERT INTO fragmento (id_documento, contenido, posicion, pagina_inicio,
            pagina_fin, embedding) VALUES (%s,'Legacy text',0,1,1,%s::vector)""",
            (document["id_documento"], json.dumps([1.0] * 1024)),
        )
    repository.initialize()
    repository.initialize()
    assert repository.health()
    with repository.connect() as connection:
        row = connection.execute(
            "SELECT f.embedding = fe.embedding AS same FROM fragmento f "
            "JOIN fragmento_embedding fe USING (id_fragmento)"
        ).fetchone()
        assert row["same"]
    assert repository.index_status()[0]["listo"]
    # Existing rows have no trusted scope, so migration keeps their vectors but hides them.
    assert repository.retrieve(
        EmbeddingSpace("bedrock", repository.settings.bedrock_model_id, "", 1024),
        [1.0] + [0.0] * 1023,
    ) == []


def test_retrieval_requires_exact_complete_space_and_rejects_stale_sources(repository, sample_pdf):
    from rag_service.errors import AppError
    from rag_service.local_embeddings import EmbeddingSpace, OllamaEmbeddingProvider
    from test_local_embeddings import OllamaAPI

    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    provider = OllamaEmbeddingProvider(repository.settings, OllamaAPI(dimensions=3))
    batch = provider.embed_many(["regulations"])
    with pytest.raises(AppError) as error:
        repository.retrieve(batch.space, batch.vectors[0])
    assert error.value.code == "index_incomplete"
    repository.prepare_local_index(provider)
    rows = repository.retrieve(batch.space, batch.vectors[0])
    assert len(rows) == 2 and repository.sources_current(rows)
    wrong = EmbeddingSpace("ollama", batch.space.model, "other-digest", 3)
    with pytest.raises(AppError):
        repository.retrieve(wrong, batch.vectors[0])
    sample_pdf.write_bytes(pdf_bytes(["New regulations."]))
    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    assert not repository.sources_current(rows)
    with pytest.raises(AppError):
        repository.retrieve(batch.space, batch.vectors[0])
    repository.prepare_local_index(provider)
    assert len(repository.retrieve(batch.space, batch.vectors[0])) == 1
    repository.delete(sample_pdf.name)
    assert repository.retrieve(batch.space, batch.vectors[0]) == []


def test_incomplete_gemini_reindex_preserves_previous_index(repository, sample_pdf):
    from types import SimpleNamespace

    from rag_service.embedding_types import EmbeddingBatch, EmbeddingSpace

    ingest(sample_pdf, repository.settings, repository, FakeProvider(), scope="institutional")
    before = repository.list_documents()
    old_space = EmbeddingSpace("bedrock", repository.settings.bedrock_model_id, "", 1024)
    target = EmbeddingSpace("gemini", "gemini-embedding-001", "v1beta", 768)
    provider = SimpleNamespace(space=target, embed_many=lambda texts: EmbeddingBatch(target, []))

    with pytest.raises(AppError) as error:
        repository.prepare_embedding_index(provider)

    assert error.value.code == "invalid_embedding"
    assert repository.list_documents() == before
    assert len(repository.retrieve(old_space, [1.0] + [0.0] * 1023)) == 2
    assert {row["proveedor"] for row in repository.index_status()} == {"bedrock"}


def test_gemini_reindex_is_resumable_and_preserves_course_permissions(repository, tmp_path):
    from rag_service.gemini import GeminiEmbeddingProvider

    repository.sync_course_catalog([18, 19])
    for key, text, scope, courses in [
        ("allowed", "COURSE EIGHTEEN MATERIAL", "course", (18,)),
        ("restricted", "COURSE NINETEEN SECRET", "course", (19,)),
        ("shared", "INSTITUTIONAL COMMON MATERIAL", "institutional", ()),
    ]:
        path = tmp_path / f"{key}.pdf"
        path.write_bytes(pdf_bytes([text]))
        ingest(path, repository.settings, repository, FakeProvider(), key=key, scope=scope,
               course_ids=courses)
    original_versions = {doc["clave"]: doc["version"] for doc in repository.list_documents()}

    def interrupted(model, payload):
        if "NINETEEN" in payload["content"]["parts"][0]["text"]:
            raise AppError("gemini_unavailable", "Interrupción del proveedor.")
        return {"embedding": {"values": [1.0] + [0.0] * 767}}

    provider = GeminiEmbeddingProvider(repository.settings, post=interrupted)
    with pytest.raises(AppError):
        repository.prepare_embedding_index(provider)
    assert not next(s for s in repository.index_status() if s["proveedor"] == "gemini")["listo"]
    with pytest.raises(AppError) as error:
        repository.retrieve(provider.space, [1.0] + [0.0] * 767, course_ids=(18, 19))
    assert error.value.code == "index_incomplete"

    def resumed(model, payload):
        assert "EIGHTEEN" not in payload["content"]["parts"][0]["text"]
        return {"embedding": {"values": [1.0] + [0.0] * 767}}

    provider = GeminiEmbeddingProvider(repository.settings, post=resumed)
    status = repository.prepare_embedding_index(provider)
    assert all(row["listo"] for row in status)
    versions = {doc["clave"]: doc["version"] for doc in repository.list_documents()}
    assert versions == original_versions
    # Production-sized statistics can move distance evaluation before join filters.
    with repository.connect() as connection:
        for table in ("fragmento_embedding", "fragmento", "documento", "espacio_embedding"):
            connection.execute(f"ANALYZE {table}")
    allowed = repository.retrieve(provider.space, [1.0] + [0.0] * 767, course_ids=(18,))
    assert {row["clave"] for row in allowed} == {"allowed", "shared"}
    common = repository.retrieve(provider.space, [1.0] + [0.0] * 767)
    assert {row["clave"] for row in common} == {"shared"}

    def already_complete(model, payload):
        raise AssertionError("No debe volver a facturar un índice completo.")

    assert repository.prepare_embedding_index(
        GeminiEmbeddingProvider(repository.settings, post=already_complete),
    ) == status
