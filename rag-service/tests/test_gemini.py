import io
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.gemini import GeminiAPI, GeminiEmbeddingProvider
from rag_service.query import GeminiChatProvider
from rag_service.conversation import ScheduleOutput


@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr("rag_service.gemini.sleep", lambda delay: None)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_gemini_chat_uses_the_configured_generate_content_endpoint(monkeypatch):
    captured = {}

    def urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response(json.dumps({"candidates": [{
            "content": {"parts": [{"text": '{"answer":"ok"}'}]},
            "finishReason": "STOP",
        }]}).encode())

    monkeypatch.setattr("rag_service.gemini.urlopen", urlopen)
    settings = Settings(_env_file=None, gemini_api_key="secret-test-key")
    provider = GeminiChatProvider(settings)
    result = provider.client.request("POST", "/api/chat", {
        "model": settings.gemini_chat_model,
        "messages": [
            {"role": "system", "content": "Rules"},
            {"role": "user", "content": "Question"},
            {"role": "assistant", "content": "Previous answer"},
        ],
        "format": {
            "type": "object", "title": "Output", "additionalProperties": False,
            "properties": {
                "answer": {"type": "string", "minLength": 1, "title": "Answer"},
            },
        },
        "options": {"temperature": 0, "num_predict": 900},
    })

    request = captured["request"]
    body = json.loads(request.data)
    assert isinstance(request, Request)
    assert request.full_url == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-latest:generateContent"
    )
    assert request.get_header("X-goog-api-key") == "secret-test-key"
    assert body["systemInstruction"]["parts"][0]["text"] == "Rules"
    assert [row["role"] for row in body["contents"]] == ["user", "model"]
    output = body["generationConfig"]["responseFormat"]["text"]
    assert output["mimeType"] == "APPLICATION_JSON"
    assert output["schema"] == {
        "type": "object", "title": "Output", "additionalProperties": False,
        "properties": {"answer": {"type": "string", "minLength": 1, "title": "Answer"}},
    }
    assert result["message"]["content"] == '{"answer":"ok"}'
    assert result["done"] is True


def test_gemini_embeddings_use_distinct_retrieval_task_types_and_fixed_dimensions():
    requests = []

    def post(model, payload):
        requests.append((model, payload))
        return {"embedding": {"values": [0.25] * 768}}

    settings = Settings(_env_file=None)
    provider = GeminiEmbeddingProvider(settings, post=post)
    document_batch = provider.embed_many(["source text"])
    query_batch = provider.embed_query("question")

    assert [row[0] for row in requests] == ["gemini-embedding-001"] * 2
    assert [row[1]["taskType"] for row in requests] == [
        "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY",
    ]
    assert all(row[1]["outputDimensionality"] == 768 for row in requests)
    assert document_batch.space.provider == query_batch.space.provider == "gemini"
    assert document_batch.space.dimensions == query_batch.space.dimensions == 768


def test_gemini_fails_closed_when_api_key_is_not_configured():
    with pytest.raises(AppError) as error:
        GeminiAPI(Settings(_env_file=None)).request("POST", "/api/chat", {})
    assert error.value.code == "gemini_configuration"


@pytest.mark.parametrize(
    ("status", "expected"), [(429, "gemini_throttled"), (503, "gemini_unavailable")],
)
def test_gemini_maps_provider_http_errors(monkeypatch, status, expected):
    def urlopen(request, timeout):
        raise HTTPError(request.full_url, status, "provider error", {}, None)

    monkeypatch.setattr("rag_service.gemini.urlopen", urlopen)
    settings = Settings(_env_file=None, gemini_api_key="secret-test-key")

    with pytest.raises(AppError) as error:
        GeminiAPI(settings).request("POST", "/api/chat", {
            "model": settings.gemini_chat_model, "messages": [],
        })

    assert error.value.code == expected


def test_gemini_maps_timeout_and_invalid_json(monkeypatch):
    settings = Settings(_env_file=None, gemini_api_key="secret-test-key")

    def timeout(request, timeout):
        raise TimeoutError

    monkeypatch.setattr("rag_service.gemini.urlopen", timeout)

    with pytest.raises(AppError) as timeout_error:
        GeminiAPI(settings).request("POST", "/api/chat", {
            "model": settings.gemini_chat_model, "messages": [],
        })
    assert timeout_error.value.code == "gemini_timeout"

    monkeypatch.setattr("rag_service.gemini.urlopen", lambda request, timeout: Response(b"{"))
    with pytest.raises(AppError) as response_error:
        GeminiAPI(settings).request("POST", "/api/chat", {
            "model": settings.gemini_chat_model, "messages": [],
        })
    assert response_error.value.code == "gemini_response"


@pytest.mark.parametrize("failure", [429, 503, 408, "timeout"])
def test_transient_failure_retries_same_model_then_returns_response(monkeypatch, failure):
    calls, delays = [], []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            if failure == "timeout":
                raise TimeoutError
            raise HTTPError(request.full_url, failure, "transient", {}, None)
        return Response(json.dumps({"candidates": [{
            "content": {"parts": [{"text": '{"answer":"OK"}'}]}, "finishReason": "STOP",
        }]}).encode())

    monkeypatch.setattr("rag_service.gemini.urlopen", urlopen)
    monkeypatch.setattr("rag_service.gemini.sleep", delays.append)
    result = GeminiAPI(Settings(_env_file=None, gemini_api_key="test")).request(
        "POST", "/api/chat", {"messages": [], "format": {"type": "object"}},
    )
    assert result["message"]["content"] == '{"answer":"OK"}'
    assert len(calls) == 2 and calls[0] == calls[1]
    assert len(delays) == 1 and 1 <= delays[0] <= 1.25


@pytest.mark.parametrize("status,attempts", [(503, 3), (400, 1), (401, 1), (403, 1)])
def test_retries_are_bounded_and_client_errors_are_not_retried(monkeypatch, status, attempts):
    calls = []

    def urlopen(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, status, "error", {}, None)

    monkeypatch.setattr("rag_service.gemini.urlopen", urlopen)
    with pytest.raises(AppError):
        GeminiAPI(Settings(_env_file=None, gemini_api_key="test", gemini_max_retries=2)).request(
            "POST", "/api/chat", {"messages": []},
        )
    assert len(calls) == attempts


def test_schedule_schema_preserves_referenced_availability(monkeypatch):
    captured = {}

    def post(settings, url, payload):
        captured.update(payload)
        return {"candidates": [{
            "content": {"parts": [{"text": "{}"}]}, "finishReason": "STOP",
        }]}

    monkeypatch.setattr("rag_service.gemini._post_json", post)
    schema = ScheduleOutput.model_json_schema()
    GeminiAPI(Settings(_env_file=None)).request("POST", "/api/chat", {
        "format": schema, "messages": [],
    })
    sent = captured["generationConfig"]["responseFormat"]["text"]["schema"]
    assert sent == schema
    assert sent["properties"]["availability"]["anyOf"][0]["$ref"] == "#/$defs/DeclaredAvailability"
    days = sent["$defs"]["DeclaredAvailability"]["properties"]["days"]
    assert days["items"]["enum"][0] == "lunes"


def test_gemini_documentary_evidence_uses_no_local_model_inventory(monkeypatch):
    from rag_service.document_evidence import extract

    quote = "Pulsa Add submission y después Save changes."

    def urlopen(request, timeout):
        body = json.loads(request.data)
        schema = body["generationConfig"]["responseFormat"]["text"]["schema"]
        if "institution_name" in schema["properties"]:
            answer = {"institution_name": ""}
        else:
            data = json.loads(body["contents"][-1]["parts"][0]["text"])
            key = next(row["passage_key"] for row in data["passages"] if row["text"] == quote)
            answer = {"draft_answer": quote, "scope_matches": True, "passage_keys": [key]}
        return Response(json.dumps({"candidates": [{
            "content": {"parts": [{"text": json.dumps(answer)}]}, "finishReason": "STOP",
        }]}).encode())

    monkeypatch.setattr("rag_service.gemini.urlopen", urlopen)
    chat = GeminiChatProvider(Settings(_env_file=None, gemini_api_key="test"))
    evidence = extract(chat, "¿Cómo agrego mi entrega?", [{
        "contenido": quote, "titulo": "Guía verificada Moodle",
    }])
    assert [(passage.source_id, passage.quote) for passage in evidence.passages] == [(1, quote)]
