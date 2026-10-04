import io
import json

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from rag_service.embeddings import BedrockEmbeddingProvider, validate_embedding
from rag_service.errors import AppError


def client():
    return boto3.client(
        "bedrock-runtime", region_name="us-east-1",
        aws_access_key_id="test", aws_secret_access_key="test",
    )


def test_bedrock_sends_v2_contract_and_checks_dimensions(settings):
    bedrock = client()
    data = json.dumps({"embedding": [1.0] + [0.0] * 1023}).encode()
    with Stubber(bedrock) as stub:
        stub.add_response("invoke_model", {
            "body": StreamingBody(io.BytesIO(data), len(data)), "contentType": "application/json",
        }, {
            "modelId": settings.bedrock_model_id, "contentType": "application/json",
            "accept": "application/json",
            "body": json.dumps({"inputText": "Reglamento", "dimensions": 1024, "normalize": True}),
        })
        vector = BedrockEmbeddingProvider(settings, bedrock).embed("Reglamento")
        assert len(vector) == 1024 and vector[0] == 1.0
        stub.assert_no_pending_responses()


def test_access_denied_becomes_safe_error(settings):
    bedrock = client()
    with Stubber(bedrock) as stub:
        stub.add_client_error("invoke_model", service_error_code="AccessDeniedException",
                              service_message="SECRET internal error")
        with pytest.raises(AppError) as error:
            BedrockEmbeddingProvider(settings, bedrock).embed("Texto")
    assert error.value.code == "bedrock_configuration"
    assert "SECRET" not in str(error.value)


def test_throttling_explains_quota_without_exposing_provider_error(settings):
    bedrock = client()
    with Stubber(bedrock) as stub:
        stub.add_client_error("invoke_model", service_error_code="ThrottlingException",
                              service_message="SECRET internal details")
        with pytest.raises(AppError) as error:
            BedrockEmbeddingProvider(settings, bedrock).embed("Texto")
    assert error.value.code == "bedrock_throttled"
    assert "cuota" in str(error.value) and "SECRET" not in str(error.value)


@pytest.mark.parametrize("code,status,expected", [
    ("ServiceUnavailableException", 503, "bedrock_unavailable"),
    ("InternalServerException", 500, "bedrock_unavailable"),
    ("ValidationException", 400, "bedrock_configuration"),
])
def test_service_errors_are_distinguished_from_configuration(settings, code, status, expected):
    bedrock = client()
    with Stubber(bedrock) as stub:
        stub.add_client_error("invoke_model", service_error_code=code, http_status_code=status)
        with pytest.raises(AppError) as error:
            BedrockEmbeddingProvider(settings, bedrock).embed("Texto")
    assert error.value.code == expected


def test_connection_error_allows_fallback(settings):
    from botocore.exceptions import EndpointConnectionError

    class Client:
        def invoke_model(self, **kwargs):
            raise EndpointConnectionError(endpoint_url="https://secret")

    with pytest.raises(AppError) as error:
        BedrockEmbeddingProvider(settings, Client()).embed("Texto")
    assert error.value.code == "bedrock_unavailable" and "secret" not in str(error.value)


@pytest.mark.parametrize("value", [None, [], [0.0] * 1536, [float("nan")] * 1024,
                                   [float("inf")] * 1024, [True] * 1024, ["0"] * 1024,
                                   [10 ** 400] * 1024])
def test_bad_vectors_are_rejected(value):
    with pytest.raises(AppError):
        validate_embedding(value)


def test_empty_input_is_rejected_without_calling_aws(settings):
    with pytest.raises(AppError) as error:
        BedrockEmbeddingProvider(settings, client()).embed("  ")
    assert error.value.code == "empty_text"


@pytest.mark.parametrize("payload", [b"not json", b"{}", b'{"embedding":[0.0]}'])
def test_malformed_bedrock_response_is_controlled_and_stream_closed(settings, payload):
    class Client:
        def __init__(self):
            self.stream = io.BytesIO(payload)

        def invoke_model(self, **kwargs):
            return {"body": self.stream}

    bedrock = Client()
    with pytest.raises(AppError) as error:
        BedrockEmbeddingProvider(settings, bedrock).embed("Texto")
    assert error.value.code == "invalid_embedding" and bedrock.stream.closed
