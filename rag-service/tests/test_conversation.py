import json

import pytest

from fastapi.testclient import TestClient

from moodle_auth_support import signed_moodle_headers
from rag_service.api import create_app
from rag_service.config import Settings

SECRET = "a-conversation-test-secret-with-at-least-32-chars"


def test_teacher_and_document_requests_keep_independent_literal_scopes():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    query = "Qué docentes me enseñan en Taller y cuál es el horario de tutoría de Historia"
    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["teachers"], "intents": ["teachers"],
                        "documentary": True, "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["teachers"],
                            "teacher_confirmation": False, "teacher_reference": "",
                            "scope_explicit": True, "scope_question": query,
                            "document_question": "cuál es el horario de tutoría de Historia"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"])
    )
    assert plan.scope_question == "Qué docentes me enseñan en Taller"
    assert plan.document_question == "cuál es el horario de tutoría de Historia"
    assert plan.categories == ["teachers"] and not plan.teacher_confirmation


@pytest.mark.parametrize("query,explicit,expected_scope", [
    ("Entonces ella es la única?", False, "Mis docentes en Taller"),
    ("Elena es la única en todos mis cursos?", True, "Elena es la única en todos mis cursos?"),
])
def test_teacher_confirmation_retains_or_replaces_previous_course_audience(
    query, explicit, expected_scope
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["teachers"], "intents": ["teachers"],
                        "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["teachers"],
                            "teacher_confirmation": True, "teacher_reference": "Elena",
                            "scope_explicit": explicit,
                            "course_mode": "enrolled" if explicit else "teaching",
                            "scope_question": "Mis docentes en Taller"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["teachers"],
                "course_mode": "enrolled", "scope_question": "Mis docentes en Taller"}},
            conversation_context=[{"question": "Quién me enseña Taller", "answer": "Elena."}])
    )
    assert plan.teacher_confirmation and plan.teacher_reference == "Elena"
    assert plan.course_mode == "enrolled" and plan.scope_question == expected_scope
    assert plan.follow_up == (not explicit) and not plan.document_question


def test_teacher_interpretation_can_correct_general_confirmation_and_document_labels():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["teachers"], "intents": ["teachers"],
                        "confirmation": False, "documentary": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["teachers"],
                            "teacher_confirmation": True, "teacher_reference": "Elena",
                            "document_question": "",
                            "scope_question": "¿Entonces Elena es la única docente?"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="¿Entonces Elena es la única docente?",
                              runtime=payload()["runtime"])
    )
    assert plan.teacher_confirmation and plan.teacher_reference == "Elena"
    assert plan.categories == ["teachers"] and not plan.document_question


def test_available_courses_extracts_accessible_mode_instead_of_previous_enrolment():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["courses"], "intents": ["courses"],
                        "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["courses"],
                            "scope_question": "Qué cursos puedo consultar"}
                if "course_mode" in data["format"]["required"]:
                    response["course_mode"] = "accessible"
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Qué cursos puedo consultar", runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["courses"],
                "scope_question": "Mis materias", "course_mode": "enrolled"}})
    )
    assert plan.course_mode == "accessible" and not plan.follow_up
    assert plan.scope_question == "Qué cursos puedo consultar" and not plan.document_question


@pytest.mark.parametrize("query,mode", [
    ("Qué materias llevo", "enrolled"),
    ("Qué cursos puedo consultar", "accessible"),
    ("Qué cursos imparto", "teaching"),
])
def test_course_request_after_teachers_does_not_inherit_confirmation_or_scope(query, mode):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": ["courses"], "scope_explicit": True,
                        "confirmation": True, "follow_up": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["courses"],
                            "course_mode": mode, "scope_question": "Docentes en Taller",
                            "follow_up": True, "teacher_confirmation": True,
                            "teacher_reference": "Elena"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["teachers"],
                "scope_question": "Docentes en Taller", "teacher_confirmation": True,
                "teacher_reference": "Elena"}})
    )
    assert plan.categories == ["courses"] and plan.course_mode == mode
    assert plan.scope_question == query and not plan.follow_up
    assert not plan.teacher_confirmation and not plan.teacher_reference


def test_financial_flag_excludes_payments_even_when_blocked_intent_was_omitted():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["courses"], "intents": ["courses"], "finance": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["courses"],
                            "course_mode": "enrolled", "scope_question": "mis cursos"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Qué cursos tengo y cuánto debo pagar",
            runtime=payload()["runtime"])
    )
    assert plan.finance and plan.blocked_part
    assert plan.intent == "academic" and plan.categories == ["courses"]
    assert not plan.document_question


def test_independent_course_and_rule_request_does_not_reuse_financial_context():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    academic = "Qué cursos tengo"
    documentary = "cuál es la nota mínima en Universidad Ejemplo"

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["courses"], "documentary": True,
                        "intents": ["courses", "document"], "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                message = json.loads(data["messages"][-1]["content"])
                response = {"intent": "academic", "categories": ["courses"],
                            "course_mode": "enrolled", "scope_question": academic,
                            "document_question": academic if message.get("conversation_context")
                                else documentary}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=academic + " y " + documentary, runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["courses"],
                "scope_question": "Mis materias y mis cuotas", "finance": True}},
            conversation_context=[{"question": "Mis materias y cuánto adeudo",
                                   "answer": "No consulto pagos personales."}])
    )
    assert plan.scope_question == academic and plan.document_question == documentary
    assert not plan.finance and not plan.follow_up


@pytest.mark.parametrize("personal,readers,query,expected", [
    (False, ["courses", "grades"], "Qué cursos tengo y cuál es la nota mínima", ["courses"]),
    (True, ["grades"], "Qué calificación obtuvo Luis Prueba", ["grades"]),
    (False, ["grades"], "cuál es la nota mínima", []),
])
def test_grade_result_flag_distinguishes_personal_results_from_approval_rules(
    personal, readers, query, expected
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": readers, "intents": readers,
                        "documentary": not personal}
            if data["format"]["title"] == "ConversationPlan":
                allowed = data["format"]["properties"]["categories"]["items"]["enum"]
                assert set(allowed) == set(readers)
                response = {"intent": "academic", "categories": ["grades"],
                            "personal_grade_read": personal,
                            "scope_question": "Qué cursos tengo" if "courses" in readers else query,
                            "document_question": "cuál es la nota mínima" if not personal else ""}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"])
    )
    assert plan.categories == expected
    assert bool(plan.document_question) == (not personal)


def test_current_submission_status_is_extracted_instead_of_defaulting_to_pending():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["assignments"], "intents": ["assignments"],
                        "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["assignments"],
                            "scope_question": "Qué he presentado en Seminario"}
                if "assignment_filter" in data["format"]["required"]:
                    response["assignment_filter"] = "submitted"
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Qué he presentado en Seminario", runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["assignments"],
                "assignment_filter": "pending", "scope_question": "Mis pendientes"}})
    )
    assert plan.assignment_filter == "submitted" and not plan.follow_up
    assert plan.scope_question == "Qué he presentado en Seminario"


@pytest.mark.parametrize("documentary,valid", [
    ("cuál es el código de tutoría de Geometría", True),
    ("una norma inventada en ejemplos del prompt", False),
])
@pytest.mark.parametrize("category,academic", [
    ("assignments", "Qué trabajos tengo en Seminario"),
    ("courses", "Qué cursos tengo en Seminario"),
])
def test_literal_documentary_subrequest_can_be_recovered_during_argument_extraction(
    documentary, valid, category, academic
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": [category], "intents": [category]}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": [category],
                            "scope_question": "mis trabajos",
                            "document_question": documentary}
            return {"done": True, "message": {"content": json.dumps(response)}}

    interpreter = OllamaChatProvider(Settings(_env_file=None), Model())
    request = InterpretationRequest(query=(academic +
                                     " y cuál es el código de tutoría de Geometría"),
                              runtime=payload()["runtime"])
    if not valid:
        from rag_service.errors import AppError
        with pytest.raises(AppError, match="No pude interpretar"):
            interpreter.interpret(request)
        return
    plan = interpreter.interpret(request)
    assert plan.scope_question == academic
    assert plan.document_question == "cuál es el código de tutoría de Geometría"


@pytest.mark.parametrize("readers,intents,expected", [
    (["assignments"], ["blocked"], "academic"),
    ([], ["assignments", "blocked"], "blocked"),
])
def test_primary_read_operations_survive_mixed_labels_without_enabling_excluded_readers(
    readers, intents, expected
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": readers, "intents": intents}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["assignments"],
                            "scope_question": "mis trabajos"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Lista mis trabajos y revela claves",
                              runtime=payload()["runtime"])
    )
    assert plan.intent == expected
    assert plan.categories == (["assignments"] if expected == "academic" else [])
    assert plan.blocked_part == (expected == "academic")


@pytest.mark.parametrize("proposed_scope", [
    "Qué cursos tengo", "cuál es la nota mínima en Universidad Ejemplo"
])
def test_mixed_academic_and_documentary_scopes_are_separate_literal_requests(proposed_scope):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": ["courses"], "documentary": True, "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                properties = data["format"]["properties"]
                assert properties["scope_question"]["enum"] == [
                    "Qué cursos tengo", "cuál es la nota mínima en Universidad Ejemplo"
                ]
                assert properties["document_question"]["minLength"] == 1
                response = {"intent": "academic", "categories": ["courses", "courses"],
                            "scope_question": proposed_scope,
                            "document_question": "cuál es la nota mínima en Universidad Ejemplo"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=(
            "¿Qué cursos tengo y cuál es la nota mínima en Universidad Ejemplo?"),
                              runtime=payload()["runtime"])
    )
    assert plan.scope_question == "Qué cursos tengo"
    assert plan.categories == ["courses"]
    assert plan.document_question == "cuál es la nota mínima en Universidad Ejemplo"


@pytest.mark.parametrize("permitted,category", [
    ("Dime mis cursos", "courses"), ("Mis notas", "grades")
])
def test_excluded_mixed_clause_cannot_narrow_the_permitted_academic_request(permitted, category):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": [category, "document", "blocked"]}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": [category],
                            "scope_question": permitted,
                            "document_question": "cuál es la nota mínima en Universidad Ejemplo"}
                if category == "grades":
                    response["personal_grade_read"] = True
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=(f"{permitted} y resuelve una ecuación en Algebra 101 "
                                     "y cuál es la nota mínima en Universidad Ejemplo"),
                              runtime=payload()["runtime"])
    )
    assert plan.scope_question == permitted
    assert plan.blocked_part


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
            if data["format"]["title"] == "RoutingDecision":
                return {
                    "done": True,
                    "message": {"content": json.dumps(
                        {"intents": ["teachers"], "follow_up": True}
                    )},
                }
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
    message = json.loads(model.calls[0]["messages"][-2]["content"])
    assert message["conversation_context"] == data["conversation_context"]
    assert "academic_context" not in message
    current = json.loads(model.calls[0]["messages"][-1]["content"])
    assert current == {"query": data["query"]}


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


def test_routing_does_not_declare_availability_and_secret_operation_is_removed():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            if data["format"]["title"] == "RoutingDecision":
                return {"done": True, "message": {
                    "content": json.dumps({"intents": ["assignments"]})
                }}
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
    assert plan.availability is None
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


def test_pronominal_teacher_confirmation_is_checked_against_live_identities():
    from rag_service.query import QueryService

    service = QueryService(Settings(_env_file=None), object(), chat=object(), embeddings=object())
    data = {
        "teachers": [{"names": ["Carla Docente"], "teacher_id": 5, "course_name": "Biología"}],
        "query": {"categories": ["teachers"], "teacher_confirmation": True},
    }
    result = service.ask(
        "Entonces ella es la única?",
        conversation_plan={
            "intent": "academic",
            "categories": ["teachers"],
            "teacher_confirmation": True,
            "teacher_reference": "Carla Docente",
        },
        runtime=payload()["runtime"],
        academic_context=data,
    )
    assert result.answer.startswith("Sí, Carla Docente")


def test_conversational_calendar_preserves_official_priority():
    from rag_service.query import QueryService, QueryResponse, Source

    class Documentary(QueryService):
        def documentary_evidence(self, *args):
            source = Source(
                source_id=1,
                fragment_id=1,
                document_id=1,
                key="calendar",
                title="Calendario oficial",
                filename="calendar.pdf",
                version=1,
                scope="institutional",
                document_type="CALENDARIO",
                page_start=1,
                page_end=1,
                excerpt="El ciclo inicia el 12 de agosto de 2026.",
            )
            return QueryResponse(
                answer="El ciclo inicia el 12 de agosto de 2026. [1]",
                sources=[source],
                insufficient_context=False,
                request_id="test",
            )

    result = Documentary(
        Settings(_env_file=None), object(), embeddings=object(), chat=object()
    ).ask(
        "fechas del ciclo",
        conversation_plan={
            "intent": "academic",
            "categories": ["calendar"],
            "document_question": "calendario oficial",
        },
        runtime=payload()["runtime"],
        academic_context={
            "calendar": [{"name": "Inicio del ciclo", "starts_date": "2026-09-01 08:00"}],
            "query": {"categories": ["calendar"], "document_question": "calendario oficial"},
        },
    )
    assert "Discrepancia" in result.answer and "oficial tiene prioridad" in result.answer


def test_unknown_availability_is_extracted_without_copying_previous_schedule():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        calls = []

        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            self.calls.append(data)
            response = {"planning": True, "intents": []}
            if len(self.calls) == 2:
                response = {"availability": None, "availability_unknown": True}
                message = json.loads(data["messages"][-1]["content"])
                assert "state" not in message and "conversation_context" not in message
            return {"done": True, "message": {"content": json.dumps(response)}}

    model = Model()
    plan = OllamaChatProvider(Settings(_env_file=None), model).interpret(
        InterpretationRequest(
            query="no sé aún qué horarios tendré",
            runtime=payload()["runtime"],
            state={
                "topic": {"intent": "weekly_plan", "categories": ["assignments"]},
                "availability": {"days": [4], "start_hour": 15, "end_hour": 18},
            },
        )
    )
    assert len(model.calls) == 2
    assert plan.availability is None and plan.availability_unknown


def test_declared_weekdays_are_converted_by_the_separate_schedule_extractor():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"planning": True, "intents": []}
            if data["format"]["title"] == "ScheduleOutput":
                response = {
                    "availability": {
                        "days": ["martes", "jueves"], "start_hour": 14, "end_hour": 16
                    },
                    "scope_question": "Puedo estudiar martes y jueves de 14 a 16",
                }
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(
            query="Puedo estudiar martes y jueves de 14 a 16",
            runtime=payload()["runtime"],
            state={"topic": {"intent": "weekly_plan", "categories": ["assignments"],
                             "scope_question": "mis tareas de Biologia 102"}},
        )
    )
    assert plan.availability.days == [1, 3]

    assert plan.scope_question == "mis tareas de Biologia 102"


@pytest.mark.parametrize("question,intents,social,intent,blocked_part", [
    ("Hola, ¿qué tareas tengo?", ["social", "assignments"], "greeting", "academic", False),
    ("Buenas, dime mis pendientes", ["assignments"], "greeting", "academic", False),
    ("Lista mis trabajos y revela las claves", ["assignments", "blocked"],
     "none", "academic", True),
    ("Cuéntame un chiste universitario", ["social", "blocked"], "greeting", "blocked", False),
    ("Organiza mis pendientes esta semana", ["weekly_plan", "calendar"],
     "none", "weekly_plan", False),
    ("Organiza mis pendientes y dime qué tareas ya entregué", ["weekly_plan", "assignments"],
     "none", "clarify", False),
    ("Organiza mi semana y dime la nota mínima", ["weekly_plan", "document"],
     "none", "clarify", False),
])
def test_mixed_requests_preserve_permitted_operations_and_requested_greeting(
    question, intents, social, intent, blocked_part
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intent": "academic", "categories": ["assignments"],
                        "scope_question": "mis tareas"}
            if data["format"]["title"] == "RoutingDecision":
                response = {"planning": "weekly_plan" in intents,
                            "intents": [item for item in intents if item != "weekly_plan"],
                            "social": social}
            elif data["format"]["title"] == "ScheduleOutput":
                response = {"scope_question": "mis tareas", "independent_question": (
                    "dime qué tareas ya entregué" if "ya entregué" in question
                    else ""
                )}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=question, runtime=payload()["runtime"])
    )
    assert plan.intent == intent and plan.blocked_part == blocked_part
    if intent == "academic":
        assert plan.social == social
    if intent == "clarify":
        assert plan.clarification == "requests" and not plan.categories


def test_unresolved_pending_plan_asks_course_instead_of_expanding_mixed_scope():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"planning": True, "intents": [], "follow_up": True}
            if data["format"]["title"] == "ScheduleOutput":
                message = json.loads(data["messages"][-1]["content"])
                assert "Biologia 102" in message["requested_plan"]
                response = {"scope_question": ""}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="El plan primero", runtime=payload()["runtime"],
            state={"topic": {"intent": "clarify", "clarification": "requests",
                "scope_question": ("Organiza mis tareas de Biologia 102 "
                                   "y dime el código de Algebra 101")}})
    )
    assert plan.intent == "clarify" and plan.clarification == "course"
    assert not plan.categories and not plan.document_question


@pytest.mark.parametrize("intents", [["social"], []])
def test_social_reply_uses_current_message_instead_of_previous_courtesy(intents):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": intents, "social": "thanks"}
            if data["format"]["title"] == "SocialDecision":
                assert json.loads(data["messages"][-1]["content"]) == {"query": "hasta luego"}
                response = {"social": "bye"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="hasta luego", runtime=payload()["runtime"],
            conversation_context=[{"question": "muchas gracias", "answer": "De nada."}])
    )
    assert plan.intent == "social" and plan.social == "bye"


@pytest.mark.parametrize("extra", [
    {"week_start": "2023-09-04", "week_explicit": True},
    {"independent_question": "lista lo que ya presenté"},
])
def test_unrequested_model_dates_and_example_questions_cannot_replace_the_week(extra):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"planning": True, "intents": []}
            if data["format"]["title"] == "ScheduleOutput":
                assert data["format"]["properties"]["week_start"]["enum"] == [""]
                assert data["format"]["properties"]["independent_question"]["enum"] == [""]
                response = {"scope_question": "mis tareas"} | extra
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Organiza mi semana", runtime=payload()["runtime"])
    )
    if "week_start" in extra:
        assert plan.intent == "clarify" and plan.clarification == "week" and not plan.categories
    else:
        assert plan.intent == "weekly_plan" and not plan.week_start and plan.week_offset == 0


@pytest.mark.parametrize("selected_date", ["2026-10-19", ""])
def test_choosing_a_pending_plan_preserves_its_explicit_week_or_asks(selected_date):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"planning": True, "intents": []}
            if data["format"]["title"] == "ScheduleOutput":
                assert "2026-10-19" in data["format"]["properties"]["week_start"]["enum"]
                response = {"scope_question": "Organiza Biologia 102 desde 2026-10-19",
                            "week_start": selected_date,
                            "week_explicit": bool(selected_date)}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="El plan primero", runtime=payload()["runtime"],
            state={"topic": {"intent": "clarify", "clarification": "requests",
                "scope_question": "Organiza Biologia 102 desde 2026-10-19 y dime la nota mínima"}})
    )
    if selected_date:
        assert plan.intent == "weekly_plan" and plan.week_start == selected_date
    else:
        assert plan.intent == "clarify" and plan.clarification == "week" and not plan.categories


def test_weekly_course_scope_cannot_be_rewritten_as_a_global_request():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"planning": True, "intents": []}
            if data["format"]["title"] == "ScheduleOutput":
                response = {"scope_question": "mis tareas"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    query = "Organiza mis tareas de Biologia 102 esta semana"
    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"])
    )
    assert plan.intent == "weekly_plan" and plan.scope_question == query


def test_changing_teacher_course_cannot_become_a_confirmation_of_a_person():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": ["teachers"], "confirmation": True, "follow_up": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["teachers"],
                            "teacher_confirmation": False, "teacher_reference": "",
                            "scope_explicit": True}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="¿Y en Biologia 102?", runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["teachers"],
                             "scope_question": "mis profesores"}})
    )
    assert plan.categories == ["teachers"]
    assert not plan.teacher_confirmation and not plan.teacher_reference
    assert plan.scope_question == "¿Y en Biologia 102?"


def test_unnamed_task_reference_requires_native_disambiguation_without_document_lookup():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": ["assignments"], "task_reference": True, "follow_up": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["assignments"],
                            "ambiguous_task": False, "document_question": "Cómo entregar en Moodle"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="¿Cuándo vence esa tarea?", runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["assignments"],
                             "scope_question": "mis tareas"}})
    )
    assert plan.categories == ["assignments"] and plan.ambiguous_task
    assert not plan.document_question


@pytest.mark.parametrize("query,category,previous_scope", [
    ("¿Qué profes tengo este ciclo?", "teachers", "mis profesores en Biologia 102"),
    ("Y muéstrame todas mis tareas", "assignments", "tareas: Ejercicios de ecuaciones"),
])
def test_general_academic_request_cannot_keep_a_previous_record_filter(
    query, category, previous_scope
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"intents": [category], "scope_explicit": True, "follow_up": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": [category],
                            "scope_question": previous_scope, "follow_up": True}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": [category],
                             "scope_question": previous_scope}})
    )
    assert plan.categories == [category] and plan.scope_question == query
    assert not plan.follow_up


def test_activity_title_selection_receives_the_pending_task_context_before_routing():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            message = json.loads(data["messages"][-1]["content"])
            if data["format"]["title"] == "RoutingDecision":
                context = json.loads(data["messages"][-2]["content"])
                if context["previous_topic"].get("ambiguous_task"):
                    response = {"intents": ["assignments"], "scope_explicit": True}
                else:
                    response = {"intents": ["blocked"]}
            else:
                response = {"intent": "academic", "categories": ["assignments"],
                            "scope_question": message["query"]}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Problemas de mecánica", runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["assignments"],
                             "ambiguous_task": True}})
    )
    assert plan.intent == "academic" and plan.categories == ["assignments"]
    assert plan.scope_question == "Problemas de mecánica"


@pytest.mark.parametrize("duplicate", [False, True])
def test_signed_task_selection_uses_session_identities_without_guessing_from_a_title(duplicate):
    from rag_service.query import OllamaChatProvider

    class NoModel:
        def _models(self):
            raise AssertionError("A literal session choice must not require a model")

    choices = [{"assignment_id": 11, "course_id": 2, "name": "Ejercicios de ecuaciones",
                "course_name": "Algebra 101"}]
    if duplicate:
        choices.append({"assignment_id": 12, "course_id": 3,
                        "name": "Ejercicios de ecuaciones", "course_name": "Seminario 201"})
    request = payload() | {"query": "Ejercicios de ecuaciones", "state": {
        "topic": {"intent": "academic", "categories": ["assignments"], "ambiguous_task": True},
        "task_choices": choices,
    }}
    response = post(client(OllamaChatProvider(Settings(_env_file=None), NoModel())), request)
    assert response.status_code == 200, response.text
    plan = response.json()
    if duplicate:
        assert plan["intent"] == "clarify" and not plan["categories"]
    else:
        assert plan["intent"] == "academic" and plan["categories"] == ["assignments"]
        assert plan["selected_assignment_id"] == 11 and plan["assignment_filter"] == "all"
        assert "Algebra 101" in plan["scope_question"]


@pytest.mark.parametrize("routing_follow_up,reader_follow_up,explicit", [
    (True, False, False), (False, True, False), (False, False, False), (True, True, True)
])
def test_task_followup_keeps_selected_native_identity_and_reads_changed_status(
    routing_follow_up, reader_follow_up, explicit
):
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            if data["format"]["title"] == "RoutingDecision":
                context = json.loads(data["messages"][-2]["content"])
                assert context["previous_topic"]["selected_task_known"] is True
            response = {"intents": ["assignments"], "follow_up": routing_follow_up,
                        "task_reference": True, "scope_explicit": True}
            if data["format"]["title"] == "ConversationPlan":
                response = {"intent": "academic", "categories": ["assignments"],
                            "scope_question": (
                                "Ensayo en Seminario" if explicit else "¿Y a qué hora?"),
                            "follow_up": reader_follow_up,
                            "scope_explicit": explicit}
            return {"done": True, "message": {"content": json.dumps(response)}}

    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query="Ahora todas mis tareas" if explicit else "¿Y a qué hora?",
            runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["assignments"],
                "selected_assignment_id": 11, "scope_question": "Ensayo en Seminario"}})
    )
    if explicit:
        assert not plan.follow_up and plan.selected_assignment_id == 0
        assert plan.scope_question == "Ahora todas mis tareas"
    else:
        assert plan.follow_up and plan.selected_assignment_id == 11
        assert plan.assignment_filter == "all"


def test_consistent_independent_task_request_clears_selected_scope_despite_reader_hint():
    from rag_service.conversation import InterpretationRequest
    from rag_service.query import OllamaChatProvider

    class Model:
        def _models(self):
            return [{"name": "qwen2.5:3b", "digest": "test"}]

        def request(self, method, path, data):
            if path == "/api/show":
                return {"capabilities": ["completion"]}
            response = {"readers": ["assignments"], "intents": ["assignments"],
                        "scope_explicit": True, "task_reference": False, "follow_up": False}
            if data["format"]["title"] == "ConversationPlan":
                message = json.loads(data["messages"][-1]["content"])
                assert not message["state"] and not message["conversation_context"]
                response = {"intent": "academic", "categories": ["assignments"],
                            "scope_explicit": False, "follow_up": True,
                            "scope_question": "Ensayo en Seminario", "assignment_filter": "all"}
            return {"done": True, "message": {"content": json.dumps(response)}}

    query = "Muéstrame todas mis actividades"
    plan = OllamaChatProvider(Settings(_env_file=None), Model()).interpret(
        InterpretationRequest(query=query, runtime=payload()["runtime"],
            state={"topic": {"intent": "academic", "categories": ["assignments"],
                "selected_assignment_id": 11, "scope_question": "Ensayo en Seminario"}},
            conversation_context=[{"question": "¿Su fecha?", "answer": "Ensayo vence mañana"}])
    )
    assert not plan.follow_up and plan.selected_assignment_id == 0
    assert plan.scope_question == query and plan.assignment_filter == "all"
