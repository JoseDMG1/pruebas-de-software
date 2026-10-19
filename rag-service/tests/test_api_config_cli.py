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
    code = main(["ingest", str(tmp_path / "missing.pdf"), "--scope", "institutional"])
    assert code == 1
    assert '"pdf_unreadable"' in capsys.readouterr().err


def test_cli_prepares_gemini_without_connecting_to_database(monkeypatch, capsys):
    import json
    from types import SimpleNamespace

    from rag_service.gemini import EmbeddingBatch, EmbeddingSpace

    settings = Settings(_env_file=None)
    monkeypatch.setattr("rag_service.cli.Settings", lambda: settings)
    monkeypatch.setattr(
        "rag_service.cli.GeminiEmbeddingProvider",
        lambda config: SimpleNamespace(embed_query=lambda text: EmbeddingBatch(
            EmbeddingSpace("gemini", config.gemini_embedding_model, "v1beta", 768),
            [[0.0] * 768],
        )),
    )
    monkeypatch.setattr(
        "rag_service.cli.GeminiChatProvider",
        lambda config: SimpleNamespace(prepare=lambda: {
            "provider": "gemini", "model": config.gemini_chat_model,
        }),
    )
    assert main(["prepare-gemini"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["provider"] == "gemini"
    assert result["chat_model"] == "gemini-flash-latest"
    assert result["embedding"]["dimensions"] == 768


def test_cli_ingestion_uses_gemini_embedding_router(monkeypatch, capsys):
    settings = Settings(_env_file=None)
    from rag_service.gemini import EmbeddingRouter

    monkeypatch.setattr("rag_service.cli.Settings", lambda: settings)

    def fake_ingest(path, config, repository, provider, **kwargs):
        assert isinstance(provider, EmbeddingRouter)
        return {"status": "indexed", "proveedor_embedding": "gemini"}

    monkeypatch.setattr("rag_service.cli.ingest", fake_ingest)
    assert main([
        "ingest", "sample.pdf", "--scope", "institutional",
    ]) == 0
    assert '"gemini"' in capsys.readouterr().out
