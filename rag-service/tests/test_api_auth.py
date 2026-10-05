import json
import time

from fastapi.testclient import TestClient

from rag_service.api import create_app
from rag_service.config import Settings
from moodle_auth_support import signed_moodle_headers


def request_body(**overrides):
    body = {"query": "¿Qué tareas me faltan?", "academic_context": {}}
    body.update(overrides)
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


class QuerySpy:
    def __init__(self):
        self.calls = []

    def ask(self, query, request_id):
        self.calls.append((query, request_id))
        return {"answer": "Respuesta", "sources": [], "insufficient_context": False,
                "request_id": request_id}


def test_query_requires_a_signed_moodle_assertion_before_calling_rag():
    secret = "test-shared-secret-that-is-long-enough"
    service = QuerySpy()
    client = TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=secret), query_service=service,
    ))

    response = client.post(
        "/api/v1/chat/query", content=request_body(), headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401
    assert service.calls == []


def test_query_fails_closed_when_moodle_authentication_is_not_configured():
    service = QuerySpy()
    client = TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=""), query_service=service,
    ))

    response = client.post(
        "/api/v1/chat/query", content=request_body(), headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 503
    assert service.calls == []


def test_local_demo_routes_are_disabled_by_default():
    client = TestClient(create_app(Settings(_env_file=None), query_service=QuerySpy()))

    assert client.get("/demo").status_code == 404
    assert client.post("/api/v1/demo/chat/query", json={"query": "pregunta"}).status_code == 404


def test_query_accepts_a_valid_signed_request_from_moodle():
    secret = "test-shared-secret-that-is-long-enough"
    service = QuerySpy()
    client = TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=secret), query_service=service,
    ))
    body = request_body()
    headers = signed_moodle_headers(secret, body, user_id="42", courses=[10, 20])

    response = client.post("/api/v1/chat/query", content=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["answer"] == "Respuesta"
    assert len(service.calls) == 1 and service.calls[0][0] == "¿Qué tareas me faltan?"


def test_query_rejects_expired_or_forged_assertions_before_calling_rag():
    secret = "test-shared-secret-that-is-long-enough"
    service = QuerySpy()
    client = TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=secret), query_service=service,
    ))
    body = request_body()
    expired_headers = signed_moodle_headers(secret, body, expires_at=int(time.time()) - 1)
    forged_parts = signed_moodle_headers(secret, body)["Authorization"].split(" ", 1)[1].split(".")
    forged_parts[2] = ("A" if forged_parts[2][0] != "A" else "B") + forged_parts[2][1:]
    forged_headers = {
        **signed_moodle_headers(secret, body),
        "Authorization": "Bearer " + ".".join(forged_parts),
    }

    for headers in (expired_headers, forged_headers):
        response = client.post(
            "/api/v1/chat/query", content=body,
            headers=headers,
        )
        assert response.status_code == 401
    assert service.calls == []


def test_query_rejects_a_body_changed_after_it_was_signed():
    secret = "test-shared-secret-that-is-long-enough"
    service = QuerySpy()
    client = TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=secret), query_service=service,
    ))
    original = request_body()
    changed = request_body(query="¿Qué notas tiene otra persona?")
    headers = signed_moodle_headers(secret, original)

    response = client.post("/api/v1/chat/query", content=changed, headers=headers)

    assert response.status_code == 401
    assert service.calls == []
