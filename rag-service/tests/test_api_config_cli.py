import pytest

pytest.importorskip("pydantic_settings")
pytest.importorskip("fastapi")
pytest.importorskip("psycopg")
pytest.importorskip("httpx")

import psycopg
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rag_service.api import create_app
from rag_service.cli import main
from rag_service.config import Settings


class HealthRepository:
    def __init__(self, available=True, fail=False):
        self.available, self.fail = available, fail

    def health(self):
        if self.fail:
            raise psycopg.OperationalError("password=secret")
        return self.available


@pytest.mark.parametrize("available,status", [(True, 200), (False, 503)])
def test_health_checks_database(available, status):
    app = create_app(Settings(_env_file=None), HealthRepository(available))
    response = TestClient(app).get("/health")
    assert response.status_code == status
    assert response.json()["database"] == ("ok" if available else "unavailable")


def test_health_connection_error_is_safe(caplog):
    with caplog.at_level("INFO", logger="rag_service"):
        app = create_app(Settings(_env_file=None), HealthRepository(fail=True))
        response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert "secret" not in response.text and "secret" not in caplog.text
    assert '"elapsed_ms"' in caplog.text and '"timestamp"' in caplog.text


def test_invalid_overlap_configuration():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_size_chars=100, chunk_overlap_chars=100)


def test_cli_errors_are_controlled(tmp_path, capsys):
    code = main(["ingest", str(tmp_path / "missing.pdf")])
    assert code == 1
    assert '"pdf_unreadable"' in capsys.readouterr().err


def test_cli_prepares_local_model_without_connecting_to_database(monkeypatch, capsys):
    import json

    from rag_service.local_embeddings import OllamaEmbeddingProvider
    from test_local_embeddings import OllamaAPI

    settings = Settings(_env_file=None)
    api = OllamaAPI([])
    monkeypatch.setattr("rag_service.cli.Settings", lambda: settings)
    monkeypatch.setattr("rag_service.cli.OllamaEmbeddingProvider",
                        lambda config: OllamaEmbeddingProvider(config, api))
    assert main(["prepare-ollama"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["provider"] == "ollama" and result["dimensions"] == 3
    assert result["model"] == settings.ollama_default_embedding_model


def test_cli_backend_override_reaches_ingestion(monkeypatch, capsys):
    settings = Settings(_env_file=None)
    monkeypatch.setattr("rag_service.cli.Settings", lambda: settings)

    def fake_ingest(path, config, repository, provider, **kwargs):
        assert config.embedding_backend == provider.settings.embedding_backend == "ollama"
        return {"status": "indexed", "proveedor_embedding": "ollama"}

    monkeypatch.setattr("rag_service.cli.ingest", fake_ingest)
    assert main(["ingest", "sample.pdf", "--backend", "ollama"]) == 0
    assert '"ollama"' in capsys.readouterr().out
