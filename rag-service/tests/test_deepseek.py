import io
import json
from urllib.error import HTTPError

import pytest

from rag_service.config import Settings
from rag_service.deepseek import DeepSeekAPI
from rag_service.errors import AppError


def test_schema_and_credentials_reach_deepseek_without_mutating_messages(monkeypatch):
    settings = Settings(_env_file=None, deepseek_api_key="test-secret")
    messages = [{"role": "user", "content": "Abre mi tarea más próxima"}]
    schema = {"type": "object", "properties": {"navigation": {"enum": ["nearest_deadline"]}}}

    def request(req, timeout):
        assert req.full_url == "https://api.deepseek.com/chat/completions"
        assert req.get_header("Authorization") == "Bearer test-secret"
        body = json.loads(req.data)
        assert body["model"] == "deepseek-flash"
        assert json.dumps(schema, ensure_ascii=False) in body["messages"][0]["content"]
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop",
            "message": {"content": '{"navigation":"nearest_deadline"}'}}]}).encode())

    monkeypatch.setattr("rag_service.deepseek.urlopen", request)
    result = DeepSeekAPI(settings).request("POST", "/api/chat", {
        "messages": messages, "format": schema,
    })
    assert result["done"] is True
    assert len(messages) == 1


@pytest.mark.parametrize("status,code", [(401, "deepseek_configuration"),
    (429, "deepseek_throttled"), (503, "deepseek_unavailable")])
def test_provider_errors_are_safe(monkeypatch, status, code):
    settings = Settings(_env_file=None, deepseek_api_key="test-secret", deepseek_max_retries=0)

    def request(req, timeout):
        raise HTTPError(req.full_url, status, "test-secret", {}, None)

    monkeypatch.setattr("rag_service.deepseek.urlopen", request)
    with pytest.raises(AppError) as error:
        DeepSeekAPI(settings).request("POST", "/api/chat", {"messages": []})
    assert error.value.code == code
    assert "test-secret" not in str(error.value)


def test_missing_key_does_not_send_a_request(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    settings = Settings(_env_file=None, deepseek_api_key=None)
    with pytest.raises(AppError, match="DEEPSEEK_API_KEY"):
        DeepSeekAPI(settings).request("POST", "/api/chat", {"messages": []})
