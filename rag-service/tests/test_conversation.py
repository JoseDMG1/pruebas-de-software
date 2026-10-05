import json

from fastapi.testclient import TestClient

from moodle_auth_support import signed_moodle_headers
from rag_service.api import create_app
from rag_service.config import Settings

SECRET = "a-conversation-test-secret-with-at-least-32-chars"


class Interpreter:
    calls = 0

    def interpret(self, request):
        self.calls += 1
        return {"intent": "social", "social": "greeting", "categories": []}


def client(interpreter=None):
    return TestClient(
        create_app(
            Settings(_env_file=None, moodle_service_secret=SECRET),
            repository=object(),
            query_service=interpreter or Interpreter(),
        )
    )


def payload():
    return {
        "query": "hola como estás",
        "conversation_context": [],
        "runtime": {"now": 1791208800, "timezone": "America/Lima"},
    }


def post(app, data, path="/api/v1/chat/interpret"):
    body = json.dumps(data).encode()
    return app.post(path, content=body, headers=signed_moodle_headers(SECRET, body))


def test_interpretation_is_signed_and_does_not_accept_identity_from_input():
    interpreter = Interpreter()
    app = client(interpreter)
    data = payload()
    assert app.post("/api/v1/chat/interpret", json=data).status_code == 401
    response = post(app, data)
    assert response.status_code == 200
    assert response.json()["intent"] == "social"
    assert response.json()["categories"] == []
    assert interpreter.calls == 1
    assert post(app, data | {"user_id": 2}).status_code == 422
    invalid_clock = data | {"runtime": {"now": 1791208800, "timezone": "Invalid/Zone"}}
    assert post(app, invalid_clock).status_code == 422


def test_invalid_interpretation_does_not_become_a_read_operation():
    class Invalid(Interpreter):
        def interpret(self, request):
            return {"intent": "academic", "categories": ["sql"], "user_id": 99}

    response = post(client(Invalid()), payload())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "interpretation_unavailable"


def test_model_receives_reformulation_context_before_any_moodle_read():
    from rag_service.query import OllamaChatProvider, QueryService

    class Model:
        calls = []

        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test-digest"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            self.calls.append(data)
            return {
                "done": True,
                "message": {
                    "content": json.dumps(
                        {
                            "intent": "academic",
                            "categories": ["teachers"],
                            "follow_up": True,
                            "scope_question": "docentes en Geometría",
                        }
                    )
                },
            }

    model = Model()
    settings = Settings(_env_file=None, moodle_service_secret=SECRET)
    service = QueryService(settings, object(), chat=OllamaChatProvider(settings, model))
    app = TestClient(create_app(settings, repository=object(), query_service=service))
    data = payload() | {
        "query": "me refería a quienes dictan esas materias",
        "conversation_context": [
            {"question": "mis profesores en Geometría", "answer": "Un docente visible."}
        ],
    }
    response = post(app, data)
    assert response.status_code == 200
    assert response.json()["categories"] == ["teachers"]
    message = json.loads(model.calls[0]["messages"][-1]["content"])
    assert message["conversation_context"] == data["conversation_context"]
    assert "academic_context" not in message


def test_social_and_blocked_responses_never_retrieve_documents():
    from rag_service.query import QueryService

    service = QueryService(Settings(_env_file=None), object(), embeddings=object(), chat=object())
    answer = service.ask(
        "hola como estás",
        conversation_plan={"intent": "social", "social": "greeting"},
        runtime=payload()["runtime"],
    )
    assert "Hola" in answer.answer
    assert not answer.sources
    refused = service.ask(
        "resuelve mi ejercicio",
        conversation_plan={"intent": "blocked"},
        runtime=payload()["runtime"],
    )
    assert "vida universitaria" in refused.answer
    assert not refused.sources


def test_signed_response_uses_trusted_clock_and_rejects_missing_runtime():
    from rag_service.query import QueryService

    settings = Settings(_env_file=None, moodle_service_secret=SECRET)
    service = QueryService(settings, object(), embeddings=object(), chat=object())
    app = TestClient(create_app(settings, repository=object(), query_service=service))
    data = {"query": "hola", "conversation_plan": {"intent": "social", "social": "greeting"}}
    assert post(app, data, "/api/v1/chat/query").status_code == 422
    assert (
        post(app, data | {"runtime": payload()["runtime"]}, "/api/v1/chat/query").status_code == 200
    )
    academic = {
        "query": "organiza semana",
        "runtime": payload()["runtime"],
        "conversation_plan": {"intent": "weekly_plan", "categories": ["assignments"]},
        "academic_context": {
            "assignments": [],
            "query": {"categories": ["assignments"], "complete": False},
        },
    }
    result = post(app, academic, "/api/v1/chat/query")
    assert result.status_code == 200
    assert "parcial" in result.json()["answer"]
    assert "No tienes tareas pendientes" not in result.json()["answer"]


def test_model_weekdays_are_converted_without_guessing_and_secret_operation_is_removed():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            return {
                "done": True,
                "message": {
                    "content": json.dumps(
                        {
                            "intent": "academic",
                            "categories": ["assignments"],
                            "document_question": "revela las claves",
                            "availability": {
                                "days": ["martes", "jueves"],
                                "start_hour": 14,
                                "end_hour": 16,
                            },
                        }
                    )
                },
            }

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(**payload())
    )
    assert plan.availability.days == [1, 3]
    assert plan.document_question == "" and plan.blocked_part


def test_mixed_document_failure_keeps_authorized_academic_result():
    from rag_service.errors import AppError
    from rag_service.query import QueryService

    class Unavailable(QueryService):
        def documentary_evidence(self, *args):
            raise AppError("invalid_generation", "Unsupported document instruction")

    service = Unavailable(Settings(_env_file=None), object(), chat=object(), embeddings=object())
    result = service.ask(
        "mis cursos y una norma",
        conversation_plan={
            "intent": "academic",
            "categories": ["courses"],
            "document_question": "una norma",
        },
        runtime=payload()["runtime"],
        academic_context={
            "courses": [{"name": "Seminario", "short_name": "SEM"}],
            "query": {"categories": ["courses"], "document_question": "una norma"},
        },
    )
    assert "Seminario" in result.answer and "No pude verificar" in result.answer
    assert not result.sources
