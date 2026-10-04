import json
import math
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError, ClientError, ConnectionError, HTTPClientError, ReadTimeoutError,
)

from rag_service.constants import EMBEDDING_DIMENSIONS
from rag_service.errors import AppError

if TYPE_CHECKING:
    from rag_service.config import Settings


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...


def validate_embedding(vector: object, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    if not isinstance(vector, list) or len(vector) != dimensions:
        raise AppError("invalid_embedding", "El embedding no tiene las dimensiones esperadas.")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        for value in vector
    ):
        raise AppError("invalid_embedding", "El embedding contiene valores inválidos.")
    try:
        values = [float(value) for value in vector]
    except OverflowError as exc:
        raise AppError("invalid_embedding", "El embedding contiene valores inválidos.") from exc
    if not all(math.isfinite(value) for value in values):
        raise AppError("invalid_embedding", "El embedding contiene valores inválidos.")
    return values


class BedrockEmbeddingProvider:
    def __init__(self, settings: "Settings", client=None):
        self.settings = settings
        self._client = client

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise AppError("empty_text", "No se puede generar un embedding de texto vacío.")
        try:
            if self._client is None:
                session = boto3.Session(
                    profile_name=self.settings.aws_profile,
                    region_name=self.settings.aws_region,
                )
                self._client = session.client(
                    "bedrock-runtime",
                    config=Config(
                        connect_timeout=5,
                        read_timeout=self.settings.bedrock_read_timeout,
                        retries={"mode": "standard", "total_max_attempts": 3},
                    ),
                )
            response = self._client.invoke_model(
                modelId=self.settings.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "inputText": text,
                    "dimensions": EMBEDDING_DIMENSIONS,
                    "normalize": True,
                }),
            )
            with response["body"] as body:
                result = json.loads(body.read())
            return validate_embedding(result["embedding"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ThrottlingException":
                raise AppError(
                    "bedrock_throttled",
                    "Bedrock rechazó la solicitud por un límite de uso. "
                    "Revise la cuota del modelo.",
                ) from exc
            retryable = exc.response.get("Error", {}).get("Code") in {
                "ServiceUnavailableException", "InternalServerException", "ModelTimeoutException",
            } or exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) >= 500
            raise AppError(
                "bedrock_unavailable" if retryable else "bedrock_configuration",
                "Bedrock no pudo generar el embedding. Revise perfil, permisos, región y conexión.",
            ) from exc
        except (ConnectionError, HTTPClientError, ReadTimeoutError) as exc:
            raise AppError("bedrock_unavailable", "No se pudo conectar con Bedrock.") from exc
        except BotoCoreError as exc:
            raise AppError(
                "bedrock_configuration",
                "Bedrock no pudo generar el embedding. Revise perfil, permisos, región y conexión.",
            ) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise AppError("invalid_embedding", "Bedrock devolvió una respuesta inválida.") from exc
