"""Gemini API clients for conversation generation and document retrieval."""

import json
import re
from random import uniform
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request

from rag_service.provider_http import urlopen

from rag_service.embedding_types import EmbeddingBatch, EmbeddingSpace
from rag_service.embeddings import validate_embedding
from rag_service.errors import AppError

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models/"
MODEL_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _api_key(settings):
    key = settings.gemini_api_key
    if key is None or not key.get_secret_value().strip():
        raise AppError("gemini_configuration", "Falta configurar GEMINI_API_KEY en el servidor.")
    return key.get_secret_value()


def _post_json(settings, url, payload):
    for attempt in range(settings.gemini_max_retries + 1):
        try:
            return _post_json_once(settings, url, payload)
        except AppError as exc:
            if exc.code not in {"gemini_throttled", "gemini_unavailable", "gemini_timeout"}:
                raise
            if attempt == settings.gemini_max_retries:
                raise
        sleep(2 ** attempt + uniform(0, 0.25))


def _post_json_once(settings, url, payload):
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": _api_key(settings)},
    )
    try:
        with urlopen(request, timeout=settings.gemini_timeout) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise AppError("gemini_response", "Gemini devolvió una respuesta inválida.")
        return result
    except HTTPError as exc:
        if exc.code == 429:
            code, message = "gemini_throttled", "Gemini rechazó la solicitud por límite de uso."
        elif exc.code == 408:
            code, message = "gemini_timeout", "Gemini agotó el tiempo de espera."
        elif exc.code in (401, 403):
            code, message = "gemini_configuration", "Gemini rechazó la credencial o el acceso."
        elif exc.code >= 500:
            code, message = "gemini_unavailable", "Gemini no está disponible temporalmente."
        else:
            code, message = "gemini_request", "Gemini rechazó la solicitud."
        raise AppError(code, message) from exc
    except (TimeoutError, URLError) as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError):
            raise AppError("gemini_timeout", "Gemini agotó el tiempo de espera.") from exc
        raise AppError("gemini_unavailable", "No se pudo conectar con Gemini.") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise AppError("gemini_response", "Gemini devolvió una respuesta inválida.") from exc


class GeminiAPI:
    """Small REST adapter that keeps prompts and credentials server-side."""

    def __init__(self, settings):
        self.settings = settings

    def request(self, method, path, payload=None):
        if method != "POST" or payload is None:
            raise AppError("gemini_request", "Operación Gemini no soportada.")
        if path != "/api/chat":
            raise AppError("gemini_request", "Operación Gemini no soportada.")
        model = payload.get("model", self.settings.gemini_chat_model)
        if not MODEL_NAME.fullmatch(model):
            raise AppError("gemini_configuration", "GEMINI_CHAT_MODEL no es válido.")
        system = []
        contents = []
        for message in payload.get("messages", []):
            role, content = message.get("role"), message.get("content")
            if role == "system":
                system.append(content)
            elif role in ("user", "assistant"):
                contents.append({
                    "role": "model" if role == "assistant" else "user",
                    "parts": [{"text": content}],
                })
            else:
                raise AppError("gemini_request", "El mensaje contiene un rol no válido.")
        options = payload.get("options", {})
        body = {
            "contents": contents,
            "generationConfig": {
                "temperature": options.get("temperature", 0),
                "maxOutputTokens": options.get("num_predict", 1200),
                "responseFormat": {"text": {
                    "mimeType": "APPLICATION_JSON", "schema": payload.get("format"),
                }},
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": "\n\n".join(system)}]}
        result = _post_json(
            self.settings, f"{API_ROOT}{quote(model, safe='')}:generateContent", body,
        )
        try:
            candidate = result["candidates"][0]
            text = "".join(part["text"] for part in candidate["content"]["parts"])
            reason = candidate.get("finishReason")
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError("gemini_response", "Gemini no devolvió contenido utilizable.") from exc
        return {
            "done": reason in ("STOP", "MAX_TOKENS"),
            "done_reason": "length" if reason == "MAX_TOKENS" else reason,
            "message": {"content": text},
        }


class GeminiEmbeddingProvider:
    def __init__(self, settings, post=None):
        self.settings = settings
        self.post = post or (lambda model, payload: _post_json(
            settings, f"{API_ROOT}{quote(model, safe='')}:embedContent", payload,
        ))

    @property
    def space(self):
        return EmbeddingSpace(
            "gemini", self.settings.gemini_embedding_model, "v1beta",
            self.settings.gemini_embedding_dimensions,
        )

    def embed_many(self, texts, *, task_type="RETRIEVAL_DOCUMENT"):
        if not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise AppError("empty_text", "No se puede generar un embedding de texto vacío.")
        model = self.settings.gemini_embedding_model
        if not MODEL_NAME.fullmatch(model):
            raise AppError("gemini_configuration", "GEMINI_EMBEDDING_MODEL no es válido.")
        vectors = []
        for text in texts:
            result = self.post(model, {
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": self.settings.gemini_embedding_dimensions,
            })
            try:
                vector = result["embedding"]["values"]
            except (KeyError, TypeError) as exc:
                raise AppError(
                    "invalid_embedding", "Gemini devolvió un embedding inválido."
                ) from exc
            vectors.append(validate_embedding(vector, self.settings.gemini_embedding_dimensions))
        return EmbeddingBatch(self.space, vectors)

    def embed_query(self, text):
        return self.embed_many([text], task_type="RETRIEVAL_QUERY")


class EmbeddingRouter:
    """Single-provider embedding router; never falls back to local or AWS models."""

    def __init__(self, settings, gemini=None):
        self.settings = settings
        self.gemini = gemini or GeminiEmbeddingProvider(settings)

    def matches(self, document):
        return (
            document["proveedor_embedding"] == "gemini"
            and document["modelo_embedding"] == self.settings.gemini_embedding_model
            and document["dimension_embedding"] == self.settings.gemini_embedding_dimensions
        )

    def embed_document(self, texts):
        return [self.gemini.embed_many(texts)], None
