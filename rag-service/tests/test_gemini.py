import io
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.gemini import GeminiAPI, GeminiEmbeddingProvider
from rag_service.query import GeminiChatProvider


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
        "format": {"type": "object", "properties": {"answer": {"type": "string"}}},
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
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["responseSchema"]["type"] == "object"
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
