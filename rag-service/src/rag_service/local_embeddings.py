"""Embeddings locales y selección por documento; nunca descarga durante la ingesta."""

import json
import logging
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rag_service.constants import EMBEDDING_DIMENSIONS
from rag_service.embeddings import BedrockEmbeddingProvider, validate_embedding
from rag_service.errors import AppError


@dataclass(frozen=True)
class EmbeddingSpace:
    provider: str
    model: str
    revision: str
    dimensions: int


@dataclass
class EmbeddingBatch:
    space: EmbeddingSpace
    vectors: list[list[float]]


class OllamaEmbeddingProvider:
    def __init__(self, settings, request=None):
        self.settings = settings
        self.request = request or self._request

    def _request(self, method, path, payload=None):
        base = self.settings.ollama_base_url.rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AppError("ollama_configuration", "OLLAMA_BASE_URL debe ser una URL HTTP válida.")
        timeout = (
            self.settings.ollama_pull_timeout if path == "/api/pull"
            else self.settings.ollama_chat_timeout if path == "/api/chat"
            else self.settings.ollama_timeout
        )
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(base + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.load(response)
            if not isinstance(result, dict) or result.get("error"):
                raise AppError("ollama_response", "Ollama devolvió una respuesta inválida.")
            return result
        except HTTPError as exc:
            raise AppError("ollama_unavailable", "Ollama rechazó la operación solicitada.") from exc
        except TimeoutError as exc:
            raise AppError("ollama_timeout", "Ollama agotó el tiempo de espera.") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AppError("ollama_timeout", "Ollama agotó el tiempo de espera.") from exc
            raise AppError("ollama_unavailable", "No se pudo conectar con Ollama.") from exc
        except OSError as exc:
            raise AppError("ollama_unavailable", "No se pudo conectar con Ollama.") from exc
        except (ValueError, TypeError) as exc:
            raise AppError("ollama_response", "Ollama devolvió una respuesta inválida.") from exc

    def _models(self):
        result = self.request("GET", "/api/tags")
        models = result.get("models")
        if not isinstance(models, list) or any(
            not isinstance(model, dict)
            or not isinstance(model.get("name"), str)
            or not isinstance(model.get("digest"), str)
            or not model["digest"]
            or not isinstance(model.get("size"), int)
            or model["size"] < 0
            for model in models
        ):
            raise AppError("ollama_response", "El inventario de Ollama es inválido.")
        return models

    def _supports_embeddings(self, name):
        result = self.request("POST", "/api/show", {"model": name})
        capabilities = result.get("capabilities")
        if not isinstance(capabilities, list):
            raise AppError("ollama_response", "Ollama debe informar las capacidades del modelo.")
        return "embedding" in capabilities

    def resolve(self):
        models = self._models()
        explicit = self.settings.ollama_embedding_model
        if explicit:
            # Ollama agrega :latest a los nombres sin etiqueta.
            name = explicit if ":" in explicit.rsplit("/", 1)[-1] else explicit + ":latest"
            candidates = [model for model in models if model["name"] == name]
        else:
            candidates = sorted(models, key=lambda model: (model["size"], model["name"]))
        for model in candidates:
            if self._supports_embeddings(model["name"]):
                return model
        if explicit and candidates:
            raise AppError("ollama_model_incompatible", "El modelo elegido no genera embeddings.")
        raise AppError(
            "ollama_model_missing",
            "No hay un modelo de embeddings compatible. Ejecute rag prepare-ollama.",
        )

    def prepare(self):
        try:
            model = self.resolve()
        except AppError as exc:
            if exc.code != "ollama_model_missing":
                raise
            name = (
                self.settings.ollama_embedding_model or self.settings.ollama_default_embedding_model
            )
            # Solo se llega aquí después de leer correctamente el inventario.
            result = self.request("POST", "/api/pull", {"model": name, "stream": False})
            if result.get("status") != "success":
                raise AppError(
                    "ollama_pull_failed", "Ollama no pudo descargar el modelo.",
                ) from None
            model = self.resolve()
        batch = self.embed_many(["Reglamento académico universitario."], model)
        return batch.space

    def embed_many(self, texts, model=None):
        if not texts or any(not text.strip() for text in texts):
            raise AppError("empty_text", "No se puede generar un embedding de texto vacío.")
        model = model or self.resolve()
        vectors = []
        dimensions = None
        for text in texts:
            result = self.request("POST", "/api/embed", {
                "model": model["name"], "input": text, "truncate": False,
                "options": {"num_ctx": self.settings.ollama_embedding_context_length},
            })
            embeddings = result.get("embeddings")
            if not isinstance(embeddings, list) or len(embeddings) != 1:
                raise AppError("invalid_embedding", "Ollama devolvió un embedding inválido.")
            vector = embeddings[0]
            if dimensions is None:
                dimensions = len(vector) if isinstance(vector, list) else 0
                if not 1 <= dimensions <= 16000:
                    raise AppError("invalid_embedding", "La dimensión local no es compatible.")
            vectors.append(validate_embedding(vector, dimensions))
        # No aceptar una etiqueta reemplazada mientras se calculaban los fragmentos.
        current = next((item for item in self._models() if item["name"] == model["name"]), None)
        if current is None or current["digest"] != model["digest"]:
            raise AppError(
                "ollama_model_changed", "El modelo cambió; vuelva a ejecutar la ingesta.",
            )
        return EmbeddingBatch(
            EmbeddingSpace("ollama", model["name"], model["digest"], dimensions), vectors,
        )

    def embed_query(self, text):
        model = self.resolve()
        if model["name"].rsplit("/", 1)[-1].startswith("qwen3-embedding:"):
            text = (
                "Instruct: Given an academic question, retrieve relevant passages "
                "that answer the query.\nQuery: " + text
            )
        return self.embed_many([text], model)


class EmbeddingRouter:
    def __init__(self, settings, bedrock=None, ollama=None, clock=time.monotonic):
        self.settings = settings
        self.bedrock = bedrock or BedrockEmbeddingProvider(settings)
        self.ollama = ollama or OllamaEmbeddingProvider(settings)
        self.clock = clock
        self.blocked_until = 0.0

    def matches(self, document):
        backend = self.settings.embedding_backend
        provider = document.get("proveedor_embedding", "bedrock")
        if backend != "auto" and backend != provider:
            return False
        if provider == "bedrock":
            return (
                document["modelo_embedding"] == self.settings.bedrock_model_id
                and document["dimension_embedding"] == EMBEDDING_DIMENSIONS
            )
        try:
            model = self.ollama.resolve()
        except AppError:
            if backend == "auto":
                return False  # Permitir una nueva ingesta con Bedrock si el local falla.
            raise
        return (
            document["modelo_embedding"] == model["name"]
            and document.get("revision_embedding") == model["digest"]
        )

    def embed_document(self, texts):
        backend = self.settings.embedding_backend
        fallback = None
        if backend == "ollama" or (backend == "auto" and self.clock() < self.blocked_until):
            return [self.ollama.embed_many(texts)], "circuit_open" if backend == "auto" else None
        try:
            # Si falla cualquier fragmento, se descarta el lote entero de Bedrock.
            vectors = [validate_embedding(self.bedrock.embed(text)) for text in texts]
        except AppError as exc:
            if backend != "auto" or exc.code not in {"bedrock_unavailable", "bedrock_throttled"}:
                raise
            self.blocked_until = self.clock() + self.settings.embedding_circuit_seconds
            return [self.ollama.embed_many(texts)], exc.code
        batches = [EmbeddingBatch(
            EmbeddingSpace("bedrock", self.settings.bedrock_model_id, "", EMBEDDING_DIMENSIONS),
            vectors,
        )]
        if backend == "auto" and self.settings.ollama_shadow_enabled:
            try:
                batches.append(self.ollama.embed_many(texts))
            except AppError as exc:
                # La copia local es auxiliar: el lote válido de Bedrock sigue siendo utilizable.
                logging.getLogger(__name__).warning("ollama_shadow_unavailable code=%s", exc.code)
                fallback = "local_shadow_unavailable"
        return batches, fallback
