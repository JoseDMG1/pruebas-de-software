import json
from urllib.error import HTTPError, URLError

import pytest

from rag_service.errors import AppError
from rag_service.local_embeddings import (
    EmbeddingRouter, EmbeddingSpace, OllamaEmbeddingProvider,
)


def model(name="local:latest", size=100, digest="sha256:a"):
    return {"name": name, "size": size, "digest": digest}


class OllamaAPI:
    def __init__(self, models=None, dimensions=3):
        self.models = models if models is not None else [model()]
        self.dimensions = dimensions
        self.calls = []
        self.chat_models = set()
        self.embeddings = None
        self.change_digest = False

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/api/tags":
            return {"models": [dict(item) for item in self.models]}
        if path == "/api/show":
            capability = "completion" if payload["model"] in self.chat_models else "embedding"
            return {"capabilities": [capability]}
        if path == "/api/pull":
            name = payload["model"]
            name = name if ":" in name else name + ":latest"
            self.models.append(model(name))
            return {"status": "success"}
        if path == "/api/embed":
            assert payload["truncate"] is False
            assert payload["options"]["num_ctx"] == 2048
            if self.change_digest:
                self.models[0]["digest"] = "sha256:changed"
            return {"embeddings": self.embeddings if self.embeddings is not None
                    else [[1.0] * self.dimensions]}
        raise AssertionError(path)


class Bedrock:
    def __init__(self, failure=None, fail_at=1):
        self.calls = []
        self.failure, self.fail_at = failure, fail_at

    def embed(self, text):
        self.calls.append(text)
        if self.failure and len(self.calls) == self.fail_at:
            raise AppError(self.failure, "Error seguro.")
        return [2.0] * 1024


def test_reuse_smallest_embedding_model_without_downloading(settings):
    api = OllamaAPI([model("chat:latest", 1), model("large:latest", 50),
                     model("small:latest", 10)])
    api.chat_models.add("chat:latest")
    space = OllamaEmbeddingProvider(settings, api).prepare()
    assert space.model == "small:latest" and space.dimensions == 3
    assert not any(path == "/api/pull" for _, path, _ in api.calls)


def test_explicit_model_takes_precedence_and_normalizes_latest(settings):
    settings.ollama_embedding_model = "large"
    api = OllamaAPI([model("small:latest", 1), model("large:latest", 100)])
    assert OllamaEmbeddingProvider(settings, api).prepare().model == "large:latest"


def test_prepare_downloads_only_after_successful_empty_inventory(settings):
    api = OllamaAPI([])
    space = OllamaEmbeddingProvider(settings, api).prepare()
    assert space.model == settings.ollama_default_embedding_model
    assert api.calls[0][1] == "/api/tags"
    pulls = [payload for _, path, payload in api.calls if path == "/api/pull"]
    assert pulls == [{"model": settings.ollama_default_embedding_model, "stream": False}]


def test_chat_model_does_not_prevent_preparing_embedding_model(settings):
    api = OllamaAPI([model("chat:latest")])
    api.chat_models.add("chat:latest")
    space = OllamaEmbeddingProvider(settings, api).prepare()
    assert space.model == settings.ollama_default_embedding_model
    assert len(api.models) == 2


def test_installed_explicit_chat_model_is_not_overwritten(settings):
    settings.ollama_embedding_model = "chat"
    api = OllamaAPI([model("chat:latest")])
    api.chat_models.add("chat:latest")
    with pytest.raises(AppError, match="no genera embeddings"):
        OllamaEmbeddingProvider(settings, api).prepare()
    assert not any(path == "/api/pull" for _, path, _ in api.calls)


def test_no_download_on_inventory_connection_failure(settings):
    calls = []

    def request(method, path, payload=None):
        calls.append(path)
        raise AppError("ollama_unavailable", "Sin acceso.")

    with pytest.raises(AppError):
        OllamaEmbeddingProvider(settings, request).prepare()
    assert calls == ["/api/tags"]


def test_ingestion_does_not_download_missing_model(settings):
    api = OllamaAPI([])
    with pytest.raises(AppError) as error:
        OllamaEmbeddingProvider(settings, api).embed_many(["Texto"])
    assert error.value.code == "ollama_model_missing"
    assert not any(path == "/api/pull" for _, path, _ in api.calls)


@pytest.mark.parametrize("embeddings", [[], [None], [[True]], [[float("nan")]],
                                        [[1], [2]], [["bad"]]])
def test_rejects_malformed_vectors(settings, embeddings):
    api = OllamaAPI()
    api.embeddings = embeddings
    with pytest.raises(AppError) as error:
        OllamaEmbeddingProvider(settings, api).embed_many(["Texto"])
    assert error.value.code == "invalid_embedding"


def test_rejects_dimension_change_between_chunks(settings):
    api = OllamaAPI()

    def request(method, path, payload=None):
        result = api(method, path, payload)
        if path == "/api/embed":
            api.dimensions += 1
        return result

    with pytest.raises(AppError):
        OllamaEmbeddingProvider(settings, request).embed_many(["Uno", "Dos"])


def test_rejects_digest_change_during_batch(settings):
    api = OllamaAPI()
    api.change_digest = True
    with pytest.raises(AppError) as error:
        OllamaEmbeddingProvider(settings, api).embed_many(["Texto"])
    assert error.value.code == "ollama_model_changed"


@pytest.mark.parametrize("error", [URLError("secret"), OSError("secret"),
                                   HTTPError("secret", 500, "secret", {}, None)])
def test_http_failures_are_safe(settings, monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr("rag_service.local_embeddings.urlopen", fail)
    with pytest.raises(AppError) as result:
        OllamaEmbeddingProvider(settings).resolve()
    assert result.value.code == "ollama_unavailable"
    assert "secret" not in str(result.value)


def test_http_contract_and_timeout(settings, monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.closed = True

        def read(self):
            return b'{"status":"success"}'

    response = Response()

    def open_request(request, timeout):
        assert request.full_url == "http://localhost:11434/api/pull"
        assert request.get_method() == "POST"
        assert json.loads(request.data) == {"model": "test", "stream": False}
        assert timeout == settings.ollama_pull_timeout
        return response

    monkeypatch.setattr("rag_service.local_embeddings.urlopen", open_request)
    assert OllamaEmbeddingProvider(settings)._request(
        "POST", "/api/pull", {"model": "test", "stream": False},
    ) == {"status": "success"}
    assert response.closed


def test_fallback_restarts_entire_document_after_partial_bedrock_failure(settings):
    api = OllamaAPI()
    bedrock = Bedrock("bedrock_throttled", fail_at=2)
    router = EmbeddingRouter(settings, bedrock, OllamaEmbeddingProvider(settings, api))
    batches, reason = router.embed_document(["Uno", "Dos", "Tres"])
    assert reason == "bedrock_throttled" and len(batches) == 1
    assert batches[0].space == EmbeddingSpace("ollama", "local:latest", "sha256:a", 3)
    assert batches[0].vectors == [[1.0] * 3] * 3
    assert bedrock.calls == ["Uno", "Dos"]
    assert [payload["input"] for _, path, payload in api.calls if path == "/api/embed"] == [
        "Uno", "Dos", "Tres",
    ]


@pytest.mark.parametrize("code", ["bedrock_configuration", "invalid_embedding", "empty_text"])
def test_configuration_and_input_errors_do_not_trigger_fallback(settings, code):
    api = OllamaAPI()
    router = EmbeddingRouter(settings, Bedrock(code), OllamaEmbeddingProvider(settings, api))
    with pytest.raises(AppError) as error:
        router.embed_document(["Texto"])
    assert error.value.code == code and not api.calls


def test_circuit_skips_bedrock_until_timeout_then_recovers(settings):
    now = [10.0]
    bedrock = Bedrock("bedrock_unavailable")
    router = EmbeddingRouter(settings, bedrock, OllamaEmbeddingProvider(settings, OllamaAPI()),
                             clock=lambda: now[0])
    assert router.embed_document(["Uno"])[1] == "bedrock_unavailable"
    now[0] += 59
    assert router.embed_document(["Dos"])[1] == "circuit_open"
    assert len(bedrock.calls) == 1
    now[0] += 2
    assert router.embed_document(["Tres"])[0][0].space.provider == "bedrock"
    assert len(bedrock.calls) == 2


def test_ollama_mode_bypasses_aws(settings):
    settings.embedding_backend = "ollama"
    bedrock = Bedrock("bedrock_configuration")
    router = EmbeddingRouter(settings, bedrock, OllamaEmbeddingProvider(settings, OllamaAPI()))
    assert router.embed_document(["Texto"])[0][0].space.provider == "ollama"
    assert not bedrock.calls


def test_bedrock_mode_does_not_fallback_or_create_local_copy(settings):
    settings.embedding_backend = "bedrock"
    api = OllamaAPI()
    router = EmbeddingRouter(settings, Bedrock("bedrock_throttled"),
                             OllamaEmbeddingProvider(settings, api))
    with pytest.raises(AppError):
        router.embed_document(["Texto"])
    router.bedrock = Bedrock()
    assert len(router.embed_document(["Texto"])[0]) == 1
    assert not api.calls


def test_successful_bedrock_creates_separate_local_copy(settings):
    router = EmbeddingRouter(settings, Bedrock(), OllamaEmbeddingProvider(settings, OllamaAPI()))
    batches, reason = router.embed_document(["Texto"])
    assert reason is None
    assert [batch.space.provider for batch in batches] == ["bedrock", "ollama"]
    assert [batch.space.dimensions for batch in batches] == [1024, 3]


def test_shadow_failure_keeps_valid_bedrock_batch(settings, caplog):
    router = EmbeddingRouter(settings, Bedrock(), OllamaEmbeddingProvider(settings, OllamaAPI([])))
    batches, reason = router.embed_document(["Texto"])
    assert len(batches) == 1 and batches[0].space.provider == "bedrock"
    assert reason == "local_shadow_unavailable"
    assert "Texto" not in caplog.text


def test_matching_uses_digest_and_provider(settings):
    api = OllamaAPI()
    router = EmbeddingRouter(settings, Bedrock(), OllamaEmbeddingProvider(settings, api))
    document = {"proveedor_embedding": "ollama", "modelo_embedding": "local:latest",
                "revision_embedding": "sha256:a", "dimension_embedding": 3}
    assert router.matches(document)
    api.models[0]["digest"] = "sha256:b"
    assert not router.matches(document)
    settings.embedding_backend = "bedrock"
    assert not router.matches(document)


def test_qwen_queries_have_retrieval_instruction_and_documents_do_not(settings):
    api = OllamaAPI([model("qwen3-embedding:0.6b")])
    provider = OllamaEmbeddingProvider(settings, api)
    provider.embed_query("¿Nota mínima?")
    provider.embed_many(["La nota mínima es 11."])
    texts = [payload["input"] for _, path, payload in api.calls if path == "/api/embed"]
    assert texts[0].startswith("Instruct:") and texts[0].endswith("Query: ¿Nota mínima?")
    assert texts[1] == "La nota mínima es 11."
