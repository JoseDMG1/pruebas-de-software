from contextlib import contextmanager
from pathlib import Path

import pytest

from rag_service.documents import ExtractedPdf, PageText
from rag_service.errors import AppError
from rag_service.ingestion import ingest


class MemoryRepository:
    def __init__(self):
        self.document = None
        self.saved_chunks = []
        self.saves = 0

    @contextmanager
    def locked(self, key):
        yield None

    def find(self, connection, key):
        return self.document

    def save(self, connection, key, title, kind, pdf, chunks, vectors, started_at, *, batches=None):
        self.saves += 1
        self.saved_chunks = chunks
        self.document = {
            "sha256": pdf.sha256, "modelo_embedding": "amazon.titan-embed-text-v2:0",
            "dimension_embedding": 1024, "chunk_size_chars": 2000, "chunk_overlap_chars": 200,
            "titulo": title, "tipo_documento": kind, "nombre_archivo": pdf.filename,
            "ruta_archivo": pdf.path, "id_documento": 1, "version": self.saves,
        }
        if batches:
            space = batches[0].space
            self.document.update(
                proveedor_embedding=space.provider, modelo_embedding=space.model,
                revision_embedding=space.revision, dimension_embedding=space.dimensions,
            )
        self.vectors = vectors
        return {"id_documento": 1, "version": self.saves, "total_fragmentos": len(chunks)}


class Provider:
    def __init__(self, fail_at=None):
        self.calls = 0
        self.fail_at = fail_at

    def embed(self, text):
        self.calls += 1
        if self.calls == self.fail_at:
            raise AppError("bedrock_unavailable", "No disponible.")
        return [1.0] + [0.0] * 1023


@pytest.fixture
def pdf(monkeypatch):
    result = ExtractedPdf("a.pdf", "/data/a.pdf", "a" * 64,
                          (PageText(1, "Texto universitario. " * 150),), 1, ())
    monkeypatch.setattr("rag_service.ingestion.extract_pdf", lambda *args: result)
    return result


def test_identical_document_skips_aws_calls_and_save(settings, pdf):
    repository = MemoryRepository()
    first = Provider()
    assert ingest(Path("a.pdf"), settings, repository, first)["status"] == "indexed"
    second = Provider()
    assert ingest(Path("a.pdf"), settings, repository, second)["status"] == "unchanged"
    assert second.calls == 0 and repository.saves == 1


def test_failure_mid_embedding_preserves_previous_document(settings, pdf):
    repository = MemoryRepository()
    ingest(Path("a.pdf"), settings, repository, Provider())
    original_document, original_chunks = repository.document, repository.saved_chunks
    with pytest.raises(AppError):
        ingest(Path("a.pdf"), settings, repository, Provider(fail_at=2), force=True)
    assert repository.saves == 1
    assert repository.document is original_document and repository.saved_chunks is original_chunks


def test_first_ingestion_failure_does_not_persist_anything(settings, pdf):
    repository = MemoryRepository()
    with pytest.raises(AppError):
        ingest(Path("a.pdf"), settings, repository, Provider(fail_at=1))
    assert repository.document is None and repository.saves == 0


def test_force_reindexes(settings, pdf):
    repository = MemoryRepository()
    ingest(Path("a.pdf"), settings, repository, Provider())
    result = ingest(Path("a.pdf"), settings, repository, Provider(), force=True)
    assert result["version"] == 2 and repository.saves == 2


def test_invalid_metadata_rejected_before_reading_pdf(settings):
    with pytest.raises(AppError) as error:
        ingest(Path("missing.pdf"), settings, MemoryRepository(), Provider(), key=" ")
    assert error.value.code == "invalid_metadata"


def test_router_fallback_saves_only_local_vectors_and_skips_unchanged(settings, pdf):
    from rag_service.local_embeddings import EmbeddingRouter, OllamaEmbeddingProvider
    from test_local_embeddings import Bedrock, OllamaAPI

    repository = MemoryRepository()
    api = OllamaAPI()
    router = EmbeddingRouter(settings, Bedrock("bedrock_throttled", fail_at=2),
                             OllamaEmbeddingProvider(settings, api))
    result = ingest(Path("a.pdf"), settings, repository, router)
    assert result["fallback"] == "bedrock_throttled"
    assert repository.document["proveedor_embedding"] == "ollama"
    assert all(len(vector) == 3 for vector in repository.vectors)
    before = len([call for call in api.calls if call[1] == "/api/embed"])
    assert ingest(Path("a.pdf"), settings, repository, router)["status"] == "unchanged"
    assert len([call for call in api.calls if call[1] == "/api/embed"]) == before


def test_both_providers_fail_preserving_previous_document(settings, pdf):
    from rag_service.local_embeddings import EmbeddingRouter, OllamaEmbeddingProvider
    from test_local_embeddings import Bedrock, OllamaAPI

    repository = MemoryRepository()
    ingest(Path("a.pdf"), settings, repository, Provider())
    previous = repository.document
    router = EmbeddingRouter(settings, Bedrock("bedrock_throttled"),
                             OllamaEmbeddingProvider(settings, OllamaAPI([])))
    with pytest.raises(AppError):
        ingest(Path("a.pdf"), settings, repository, router, force=True)
    assert repository.document is previous and repository.saves == 1
