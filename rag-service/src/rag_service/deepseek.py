"""DeepSeek chat API adapter for interpretation and answer generation."""

import json
import re
from random import uniform
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request

from rag_service.provider_http import urlopen

from rag_service.errors import AppError

MODEL_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _api_key(settings):
    key = settings.deepseek_api_key
    if key is None or not key.get_secret_value().strip():
        raise AppError(
            "deepseek_configuration", "Falta configurar DEEPSEEK_API_KEY en el servidor."
        )
    return key.get_secret_value()


def _post_json(settings, payload):
    for attempt in range(settings.deepseek_max_retries + 1):
        try:
            return _post_json_once(settings, payload)
        except AppError as exc:
            if exc.code not in {"deepseek_throttled", "deepseek_unavailable", "deepseek_timeout"}:
                raise
            if attempt == settings.deepseek_max_retries:
                raise
        sleep(2 ** attempt + uniform(0, 0.25))


def _post_json_once(settings, payload):
    base_url = settings.deepseek_base_url.rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise AppError("deepseek_configuration", "DEEPSEEK_BASE_URL debe ser una URL HTTPS válida.")
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key(settings)}",
        },
    )
    try:
        with urlopen(request, timeout=settings.deepseek_timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise AppError("deepseek_response", "DeepSeek devolvió una respuesta inválida.")
        return result
    except HTTPError as exc:
        if exc.code == 429:
            code, message = "deepseek_throttled", "DeepSeek rechazó la solicitud por límite de uso."
        elif exc.code in (408, 504):
            code, message = "deepseek_timeout", "DeepSeek agotó el tiempo de espera."
        elif exc.code in (401, 403):
            code, message = "deepseek_configuration", "DeepSeek rechazó la credencial o el acceso."
        elif exc.code >= 500:
            code, message = "deepseek_unavailable", "DeepSeek no está disponible temporalmente."
        else:
            code, message = "deepseek_request", "DeepSeek rechazó la solicitud."
        raise AppError(code, message) from exc
    except (TimeoutError, URLError) as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError):
            raise AppError("deepseek_timeout", "DeepSeek agotó el tiempo de espera.") from exc
        raise AppError("deepseek_unavailable", "No se pudo conectar con DeepSeek.") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise AppError("deepseek_response", "DeepSeek devolvió una respuesta inválida.") from exc


class DeepSeekAPI:
    """Translate the chat-provider contract to DeepSeek Chat Completions."""

    def __init__(self, settings):
        self.settings = settings

    def request(self, method, path, payload=None):
        if method != "POST" or path != "/api/chat" or payload is None:
            raise AppError("deepseek_request", "Operación DeepSeek no soportada.")
        model = payload.get("model", self.settings.deepseek_chat_model)
        if not MODEL_NAME.fullmatch(model):
            raise AppError("deepseek_configuration", "DEEPSEEK_CHAT_MODEL no es válido.")
        options = payload.get("options", {})
        messages = [dict(message) for message in payload.get("messages", [])]
        if payload.get("format"):
            instruction = ("Responde solo un objeto JSON conforme a este esquema JSON Schema: "
                           + json.dumps(payload["format"], ensure_ascii=False))
            messages.insert(0, {"role": "system", "content": instruction})
        body = {
            "model": model,
            "messages": messages,
            "temperature": options.get("temperature", 0),
            "stream": False,
            "max_tokens": options.get("num_predict", 1200),
            # RAG needs short structured output; avoid the default thinking-mode tokens.
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
        }
        result = _post_json(self.settings, body)
        try:
            choice = result["choices"][0]
            content = choice["message"]["content"]
            reason = choice["finish_reason"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError(
                "deepseek_response", "DeepSeek no devolvió contenido utilizable."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AppError("deepseek_response", "DeepSeek devolvió contenido vacío.")
        return {
            "done": reason == "stop",
            "done_reason": "length" if reason == "length" else reason,
            "message": {"content": content},
        }
