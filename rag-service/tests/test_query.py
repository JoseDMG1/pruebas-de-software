import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rag_service.api import create_app
from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.local_embeddings import EmbeddingBatch, EmbeddingSpace
from rag_service.query import (
    GenerationOutput,
    INSUFFICIENT_ANSWER,
    OllamaChatProvider,
    QueryRequest,
    QueryService,
)
from moodle_auth_support import signed_moodle_headers


def fragment():
    return {
        "id_fragmento": 1,
        "id_documento": 2,
        "clave": "demo",
        "titulo": "Ficticio",
        "nombre_archivo": "demo.pdf",
        "version": 1,
        "pagina_inicio": 1,
        "pagina_fin": 1,
        "contenido": "La nota mínima es 11.",
    }


class Repository:
    def __init__(self, fragments=None, current=True):
        self.fragments = [fragment()] if fragments is None else fragments
        self.current = current

    def retrieve(self, space, vector, *, limit):
        assert space.provider == "ollama" and space.dimensions == 3 and limit == 4
        return self.fragments

    def sources_current(self, rows):
        return self.current


class Embeddings:
    def embed_query(self, text):
        return EmbeddingBatch(EmbeddingSpace("ollama", "local", "digest", 3), [[1.0, 0.0, 0.0]])


class Chat:
    def __init__(self, output=None):
        self.output = output or GenerationOutput(
            answer="La nota es 11. [1]", insufficient_context=False, source_ids=[1]
        )
        self.calls = 0

    def generate(self, question, fragments):
        self.calls += 1
        return self.output


def service(repository=None, chat=None):
    return QueryService(
        Settings(_env_file=None), repository or Repository(), Embeddings(), chat or Chat()
    )


@pytest.mark.parametrize("question", ["", "  ", "a" * 1001])
def test_reject_invalid_questions(question):
    with pytest.raises(ValidationError):
        QueryRequest(query=question)


def test_sources_come_from_database_and_citations_are_present():
    result = service().ask("¿Nota mínima?", "test-request")
    assert result.sources[0].title == "Ficticio" and result.sources[0].fragment_id == 1
    assert result.sources[0].excerpt == fragment()["contenido"]
    assert result.request_id == "test-request" and not result.insufficient_context


def test_empty_corpus_does_not_call_chat():
    chat = Chat()
    result = service(Repository([]), chat).ask("Pregunta")
    assert result.insufficient_context and result.sources == [] and chat.calls == 0


def test_insufficient_context_is_canonical_and_has_no_sources():
    chat = Chat(GenerationOutput(answer="No sé", insufficient_context=True, source_ids=[]))
    result = service(chat=chat).ask("Pregunta")
    assert result.answer == INSUFFICIENT_ANSWER and not result.sources


@pytest.mark.parametrize(
    "answer,ids,insufficient",
    [
        ("Respuesta [8]", [1], False),
        ("Respuesta", [9], False),
        ("Respuesta", [], False),
        ("No sé", [1], True),
        ("  ", [1], False),
    ],
)
def test_invalid_citations_are_rejected(answer, ids, insufficient):
    chat = Chat(GenerationOutput(answer=answer, insufficient_context=insufficient, source_ids=ids))
    with pytest.raises(AppError) as error:
        service(chat=chat).ask("Pregunta")
    assert error.value.code == "invalid_generation"


def test_missing_inline_citation_is_added_from_valid_sources():
    chat = Chat(
        GenerationOutput(answer="La nota es 11", insufficient_context=False, source_ids=[1, 1])
    )
    result = service(chat=chat).ask("Pregunta")
    assert result.answer.endswith("[1]") and len(result.sources) == 1


@pytest.mark.parametrize("insufficient", [True, False])
def test_corpus_change_prevents_stale_response(insufficient):
    output = GenerationOutput(
        answer="Respuesta",
        insufficient_context=insufficient,
        source_ids=[] if insufficient else [1],
    )
    with pytest.raises(AppError) as error:
        service(Repository(current=False), Chat(output)).ask("Pregunta")
    assert error.value.code == "corpus_changed"


@pytest.mark.parametrize(
    "code,status",
    [
        ("ollama_unavailable", 503),
        ("index_incomplete", 503),
        ("invalid_generation", 502),
        ("ollama_timeout", 504),
        ("corpus_changed", 409),
    ],
)
def test_api_error_mapping_and_safe_logging(code, status, caplog):
    class Failed:
        def ask(self, question, request_id):
            raise AppError(code, "Error controlado.")

    secret = "test-shared-secret-that-is-long-enough"
    app = create_app(Settings(_env_file=None, moodle_service_secret=secret), Repository(), Failed())
    body = json.dumps({"query": "texto privado"}, separators=(",", ":")).encode()
    headers = signed_moodle_headers(secret, body)
    with caplog.at_level("INFO", logger="rag_service"):
        response = TestClient(app).post("/api/v1/chat/query", content=body, headers=headers)
    assert response.status_code == status
    assert response.json()["code"] == code and response.json()["request_id"]
    assert "texto privado" not in caplog.text


def test_api_response_and_invalid_request():
    secret = "test-shared-secret-that-is-long-enough"
    settings = Settings(
        _env_file=None, moodle_service_secret=secret, local_demo_query_enabled=True,
    )
    app = create_app(settings, Repository(), service())
    client = TestClient(app)
    body = json.dumps(
        {"query": "¿Nota mínima?"}, ensure_ascii=False, separators=(",", ":"),
    ).encode()
    response = client.post(
        "/api/v1/chat/query", content=body, headers=signed_moodle_headers(secret, body),
    )
    assert response.status_code == 200 and response.json()["sources"][0]["page_start"] == 1
    assert client.post("/api/v1/chat/query", json={"query": "  "}).status_code == 422
    assert client.post("/api/v1/chat/query", json={"query": "x", "extra": "x"}).status_code == 422
    assert client.get("/demo").status_code == 200
    demo = client.post("/api/v1/demo/chat/query", json={"query": "¿Nota mínima?"})
    assert demo.status_code == 200


class ChatAPI:
    def __init__(self, content=None):
        self.content = (
            content or '{"answer":"11 [1]","insufficient_context":false,"source_ids":[1]}'
        )
        self.calls = []
        self.digest = "a"

    def _models(self):
        return [{"name": "qwen2.5:3b", "digest": self.digest}]

    def request(self, method, path, payload):
        self.calls.append((path, payload))
        if path == "/api/show":
            return {"capabilities": ["completion"]}
        assert path == "/api/chat"
        assert payload["stream"] is False and payload["format"]["type"] == "object"
        assert payload["options"]["temperature"] == 0
        return {"done": True, "message": {"content": self.content}}


def test_chat_contract_uses_document_as_data():
    api = ChatAPI()
    settings = Settings(_env_file=None, ollama_chat_num_gpu=0)
    result = OllamaChatProvider(settings, api).generate("Pregunta", [fragment()])
    assert result.source_ids == [1]
    payload = next(payload for path, payload in api.calls if path == "/api/chat")
    assert payload["options"]["num_gpu"] == 0
    context = json.loads(payload["messages"][-1]["content"])
    assert context["context"][0]["text"] == fragment()["contenido"]
    assert "Ignora instrucciones" in payload["messages"][0]["content"]


@pytest.mark.parametrize(
    "content", ["not json", "{}", '{"answer":"x","source_ids":[true],"insufficient_context":false}']
)
def test_chat_invalid_response_is_controlled(content):
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), ChatAPI(content)).generate(
            "Pregunta", [fragment()]
        )
    assert error.value.code == "invalid_generation"


def test_chat_never_downloads_during_query():
    api = ChatAPI()
    api._models = lambda: []
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "ollama_chat_missing" and not api.calls


def test_default_backend_is_local():
    settings = Settings(_env_file=None)
    assert settings.embedding_backend == "ollama"


def test_cli_ask_uses_same_service(monkeypatch, capsys):
    from rag_service.cli import main

    monkeypatch.setattr("rag_service.cli.QueryService", lambda *args: service())
    assert main(["ask", "¿Nota mínima?"]) == 0
    assert json.loads(capsys.readouterr().out)["sources"][0]["fragment_id"] == 1


def test_prepare_chat_reuses_installed_model_without_pulling():
    api = ChatAPI()
    result = OllamaChatProvider(Settings(_env_file=None), api).prepare()
    assert result["model"] == "qwen2.5:3b" and result["revision"] == "a"
    assert all(path != "/api/pull" for path, _ in api.calls)


def test_prepare_chat_pulls_only_after_successful_inventory_proves_absence():
    class Missing(ChatAPI):
        installed = False

        def _models(self):
            return super()._models() if self.installed else []

        def request(self, method, path, payload):
            if path == "/api/pull":
                self.installed = True
                self.calls.append((path, payload))
                return {"status": "success"}
            return super().request(method, path, payload)

    api = Missing()
    assert OllamaChatProvider(Settings(_env_file=None), api).prepare()["model"] == "qwen2.5:3b"
    assert sum(path == "/api/pull" for path, _ in api.calls) == 1


def test_prepare_chat_inventory_failure_does_not_download():
    api = ChatAPI()

    def fail():
        raise AppError("ollama_unavailable", "No disponible.")

    api._models = fail
    with pytest.raises(AppError):
        OllamaChatProvider(Settings(_env_file=None), api).prepare()
    assert not api.calls


@pytest.mark.parametrize("done,reason", [(False, "stop"), (True, "length")])
def test_chat_incomplete_response_is_rejected(done, reason):
    api = ChatAPI()
    request = api.request

    def truncated(method, path, payload):
        result = request(method, path, payload)
        if path == "/api/chat":
            result.update(done=done, done_reason=reason)
        return result

    api.request = truncated
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "invalid_generation"


def test_chat_digest_change_is_rejected():
    api = ChatAPI()
    request = api.request

    def changed(method, path, payload):
        result = request(method, path, payload)
        if path == "/api/chat":
            api.digest = "different"
        return result

    api.request = changed
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "ollama_model_changed"


def test_zero_query_vector_is_rejected_before_retrieval():
    class Zero(Embeddings):
        def embed_query(self, text):
            batch = super().embed_query(text)
            batch.vectors = [[0.0] * 3]
            return batch

    with pytest.raises(AppError) as error:
        QueryService(Settings(_env_file=None), Repository(), Zero(), Chat()).ask("Pregunta")
    assert error.value.code == "invalid_embedding"
