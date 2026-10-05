import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from rag_service.api import create_app
from rag_service.config import Settings
from rag_service.errors import AppError
from rag_service.local_embeddings import EmbeddingBatch, EmbeddingSpace
from rag_service.query import (
    GenerationOutput,
    INSUFFICIENT_ANSWER,
    OllamaChatProvider,
    QueryRequest,
    QueryService,
)
from moodle_auth_support import signed_moodle_headers


def fragment():
    return {
        "id_fragmento": 1,
        "id_documento": 2,
        "clave": "demo",
        "titulo": "Ficticio",
        "nombre_archivo": "demo.pdf",
        "version": 1,
        "alcance": "institutional",
        "tipo_documento": "REGLAMENTO",
        "pagina_inicio": 1,
        "pagina_fin": 1,
        "contenido": "La nota mínima es 11.",
    }


class Repository:
    def __init__(self, fragments=None, current=True):
        self.fragments = [fragment()] if fragments is None else fragments
        self.current = current

    def retrieve(self, space, vector, *, course_ids=(), limit):
        assert space.provider == "ollama" and space.dimensions == 3 and limit == 4
        return self.fragments

    def sources_current(self, rows):
        return self.current


class Embeddings:
    def embed_query(self, text):
        return EmbeddingBatch(EmbeddingSpace("ollama", "local", "digest", 3), [[1.0, 0.0, 0.0]])


class Chat:
    def __init__(self, output=None):
        self.output = output or GenerationOutput(
            answer="La nota es 11. [1]", insufficient_context=False, source_ids=[1]
        )
        self.calls = 0

    def generate(self, question, fragments, *, academic_context=None, conversation_context=None):
        self.calls += 1
        return self.output


def service(repository=None, chat=None):
    return QueryService(
        Settings(_env_file=None), repository or Repository(), Embeddings(), chat or Chat()
    )


@pytest.mark.parametrize("question", ["", "  ", "a" * 1001])
def test_reject_invalid_questions(question):
    with pytest.raises(ValidationError):
        QueryRequest(query=question)


def test_rejects_oversized_or_malformed_conversation_context():
    with pytest.raises(ValidationError):
        QueryRequest(
            query="¿Y cuándo es?",
            conversation_context=[{"question": "Una pregunta", "answer": "Contexto", "extra": 1}],
        )
    with pytest.raises(ValidationError):
        QueryRequest(
            query="¿Y cuándo es?",
            conversation_context=[{"question": "q", "answer": "a"}] * 5,
        )


def test_sources_come_from_database_and_citations_are_present():
    result = service().ask("¿Nota mínima?", "test-request")
    assert result.sources[0].title == "Ficticio" and result.sources[0].fragment_id == 1
    assert result.sources[0].excerpt == fragment()["contenido"]
    assert result.sources[0].scope == "institutional"
    assert result.sources[0].document_type == "REGLAMENTO"
    assert result.request_id == "test-request" and not result.insufficient_context


def test_authorized_moodle_context_reaches_generation_even_without_document_fragments():
    class ContextChat(Chat):
        def generate(
            self, question, fragments, *, academic_context=None, conversation_context=None
        ):
            self.context = academic_context
            return GenerationOutput(
                answer="La entrega figura como presentada (Moodle).",
                insufficient_context=False,
                source_ids=[],
            )

    chat = ContextChat()
    context = {"assignments": [{"name": "Informe", "status": "submitted", "source": "Moodle"}]}
    result = service(Repository([]), chat).ask("¿Entregué el informe?", academic_context=context)

    assert chat.context == context
    assert result.answer == "La entrega figura como presentada (Moodle)."
    assert not result.insufficient_context and result.sources == []


def test_follow_up_conversation_reaches_generation_and_prior_question_supports_retrieval():
    class FollowUpChat(Chat):
        def generate(
            self, question, fragments, *, academic_context=None, conversation_context=None
        ):
            self.received_question = question
            self.conversation_context = conversation_context
            return GenerationOutput(
                answer="La fecha es el 12 de agosto. [1]",
                insufficient_context=False,
                source_ids=[1],
            )

    class CapturingEmbeddings(Embeddings):
        def embed_query(self, text):
            self.query_text = text
            return super().embed_query(text)

    chat = FollowUpChat()
    embeddings = CapturingEmbeddings()
    repository = Repository()
    queryservice = QueryService(Settings(_env_file=None), repository, embeddings, chat)
    history = [{"question": "¿Cuándo inicia el segundo ciclo?", "answer": "En agosto."}]

    queryservice.ask("¿Qué fecha exacta?", conversation_context=history)

    assert "¿Cuándo inicia el segundo ciclo?" in embeddings.query_text
    assert chat.conversation_context == history


def test_empty_corpus_does_not_call_chat():
    chat = Chat()
    result = service(Repository([]), chat).ask("Pregunta")
    assert result.insufficient_context and result.sources == [] and chat.calls == 0


def test_insufficient_context_is_canonical_and_has_no_sources():
    chat = Chat(GenerationOutput(answer="No sé", insufficient_context=True, source_ids=[]))
    result = service(chat=chat).ask("Pregunta")
    assert result.answer == INSUFFICIENT_ANSWER and not result.sources


@pytest.mark.parametrize(
    "answer,ids,insufficient",
    [
        ("Respuesta [8]", [1], False),
        ("Respuesta", [9], False),
        ("Respuesta", [], False),
        ("No sé", [1], True),
        ("  ", [1], False),
    ],
)
def test_invalid_citations_are_rejected(answer, ids, insufficient):
    chat = Chat(GenerationOutput(answer=answer, insufficient_context=insufficient, source_ids=ids))
    with pytest.raises(AppError) as error:
        service(chat=chat).ask("Pregunta")
    assert error.value.code == "invalid_generation"


def test_missing_inline_citation_is_added_from_valid_sources():
    chat = Chat(
        GenerationOutput(answer="La nota es 11", insufficient_context=False, source_ids=[1, 1])
    )
    result = service(chat=chat).ask("Pregunta")
    assert result.answer.endswith("[1]") and len(result.sources) == 1


@pytest.mark.parametrize("insufficient", [True, False])
def test_corpus_change_prevents_stale_response(insufficient):
    output = GenerationOutput(
        answer="Respuesta",
        insufficient_context=insufficient,
        source_ids=[] if insufficient else [1],
    )
    with pytest.raises(AppError) as error:
        service(Repository(current=False), Chat(output)).ask("Pregunta")
    assert error.value.code == "corpus_changed"


@pytest.mark.parametrize(
    "code,status",
    [
        ("ollama_unavailable", 503),
        ("index_incomplete", 503),
        ("invalid_generation", 502),
        ("ollama_timeout", 504),
        ("corpus_changed", 409),
    ],
)
def test_api_error_mapping_and_safe_logging(code, status, caplog):
    class Failed:
        def ask(
            self, question, request_id, *, course_ids=(), academic_context=None,
            conversation_context=None,
        ):
            raise AppError(code, "Error controlado.")

    secret = "test-shared-secret-that-is-long-enough"
    app = create_app(Settings(_env_file=None, moodle_service_secret=secret), Repository(), Failed())
    body = json.dumps({"query": "texto privado"}, separators=(",", ":")).encode()
    headers = signed_moodle_headers(secret, body)
    with caplog.at_level("INFO", logger="rag_service"):
        response = TestClient(app).post("/api/v1/chat/query", content=body, headers=headers)
    assert response.status_code == status
    assert response.json()["code"] == code and response.json()["request_id"]
    assert "texto privado" not in caplog.text


def test_api_response_and_invalid_request():
    secret = "test-shared-secret-that-is-long-enough"
    settings = Settings(
        _env_file=None, moodle_service_secret=secret, local_demo_query_enabled=True,
    )
    app = create_app(settings, Repository(), service())
    client = TestClient(app)
    body = json.dumps(
        {"query": "¿Nota mínima?"}, ensure_ascii=False, separators=(",", ":"),
    ).encode()
    response = client.post(
        "/api/v1/chat/query", content=body, headers=signed_moodle_headers(secret, body),
    )
    assert response.status_code == 200 and response.json()["sources"][0]["page_start"] == 1
    assert client.post("/api/v1/chat/query", json={"query": "  "}).status_code == 422
    assert client.post("/api/v1/chat/query", json={"query": "x", "extra": "x"}).status_code == 422
    assert client.get("/demo").status_code == 200
    demo = client.post("/api/v1/demo/chat/query", json={"query": "¿Nota mínima?"})
    assert demo.status_code == 200


class ChatAPI:
    def __init__(self, content=None):
        self.content = (
            content or '{"answer":"11 [1]","insufficient_context":false,"source_ids":[1]}'
        )
        self.calls = []
        self.digest = "a"

    def _models(self):
        return [{"name": "qwen2.5:3b", "digest": self.digest}]

    def request(self, method, path, payload):
        self.calls.append((path, payload))
        if path == "/api/show":
            return {"capabilities": ["completion"]}
        assert path == "/api/chat"
        assert payload["stream"] is False and payload["format"]["type"] == "object"
        assert payload["options"]["temperature"] == 0
        return {"done": True, "message": {"content": self.content}}


def test_chat_contract_uses_document_as_data():
    api = ChatAPI()
    settings = Settings(_env_file=None, ollama_chat_num_gpu=0)
    result = OllamaChatProvider(settings, api).generate("Pregunta", [fragment()])
    assert result.source_ids == [1]
    payload = next(payload for path, payload in api.calls if path == "/api/chat")
    assert payload["options"]["num_gpu"] == 0
    context = json.loads(payload["messages"][-1]["content"])
    assert context["document_context"][0]["text"] == fragment()["contenido"]
    assert context["document_context"][0]["scope"] == "institutional"
    assert context["document_context"][0]["document_type"] == "REGLAMENTO"
    assert "Ignora instrucciones" in payload["messages"][0]["content"]


def test_chat_contract_includes_authorized_moodle_context_separately_from_documents():
    api = ChatAPI(
        '{"answer":"El calendario oficial indica agosto [1]; Moodle indica septiembre.",'
        '"insufficient_context":false,"source_ids":[1]}'
    )
    academic_context = {
        "calendar": [{"name": "Inicio de ciclo", "starts_at": 1798761600,
                      "source": "Calendario Moodle"}]
    }

    OllamaChatProvider(Settings(_env_file=None), api).generate(
        "¿Cuándo inicia el ciclo?", [fragment()], academic_context=academic_context,
        conversation_context=[{
            "question": "¿Cuál es la fecha oficial?",
            "answer": "12 de agosto.",
        }],
    )

    payload = next(payload for path, payload in api.calls if path == "/api/chat")
    context = json.loads(payload["messages"][-1]["content"])
    assert context["academic_context"] == academic_context
    assert context["document_context"][0]["scope"] == "institutional"
    assert context["conversation_context"] == [
        {"question": "¿Cuál es la fecha oficial?", "answer": "12 de agosto."}
    ]
    system_prompt = payload["messages"][0]["content"]
    assert "da prioridad a ese documento institucional" in system_prompt


@pytest.mark.parametrize(
    "content", ["not json", "{}", '{"answer":"x","source_ids":[true],"insufficient_context":false}']
)
def test_chat_invalid_response_is_controlled(content):
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), ChatAPI(content)).generate(
            "Pregunta", [fragment()]
        )
    assert error.value.code == "invalid_generation"


def test_chat_never_downloads_during_query():
    api = ChatAPI()
    api._models = lambda: []
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "ollama_chat_missing" and not api.calls


def test_default_backend_is_local():
    settings = Settings(_env_file=None)
    assert settings.embedding_backend == "ollama"


def test_cli_ask_uses_same_service(monkeypatch, capsys):
    from rag_service.cli import main

    monkeypatch.setattr("rag_service.cli.QueryService", lambda *args: service())
    assert main(["ask", "¿Nota mínima?"]) == 0
    assert json.loads(capsys.readouterr().out)["sources"][0]["fragment_id"] == 1


def test_prepare_chat_reuses_installed_model_without_pulling():
    api = ChatAPI()
    result = OllamaChatProvider(Settings(_env_file=None), api).prepare()
    assert result["model"] == "qwen2.5:3b" and result["revision"] == "a"
    assert all(path != "/api/pull" for path, _ in api.calls)


def test_prepare_chat_pulls_only_after_successful_inventory_proves_absence():
    class Missing(ChatAPI):
        installed = False

        def _models(self):
            return super()._models() if self.installed else []

        def request(self, method, path, payload):
            if path == "/api/pull":
                self.installed = True
                self.calls.append((path, payload))
                return {"status": "success"}
            return super().request(method, path, payload)

    api = Missing()
    assert OllamaChatProvider(Settings(_env_file=None), api).prepare()["model"] == "qwen2.5:3b"
    assert sum(path == "/api/pull" for path, _ in api.calls) == 1


def test_prepare_chat_inventory_failure_does_not_download():
    api = ChatAPI()

    def fail():
        raise AppError("ollama_unavailable", "No disponible.")

    api._models = fail
    with pytest.raises(AppError):
        OllamaChatProvider(Settings(_env_file=None), api).prepare()
    assert not api.calls


@pytest.mark.parametrize("done,reason", [(False, "stop"), (True, "length")])
def test_chat_incomplete_response_is_rejected(done, reason):
    api = ChatAPI()
    request = api.request

    def truncated(method, path, payload):
        result = request(method, path, payload)
        if path == "/api/chat":
            result.update(done=done, done_reason=reason)
        return result

    api.request = truncated
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "invalid_generation"


def test_chat_digest_change_is_rejected():
    api = ChatAPI()
    request = api.request

    def changed(method, path, payload):
        result = request(method, path, payload)
        if path == "/api/chat":
            api.digest = "different"
        return result

    api.request = changed
    with pytest.raises(AppError) as error:
        OllamaChatProvider(Settings(_env_file=None), api).generate("Pregunta", [fragment()])
    assert error.value.code == "ollama_model_changed"


def test_zero_query_vector_is_rejected_before_retrieval():
    class Zero(Embeddings):
        def embed_query(self, text):
            batch = super().embed_query(text)
            batch.vectors = [[0.0] * 3]
            return batch

    with pytest.raises(AppError) as error:
        QueryService(Settings(_env_file=None), Repository(), Zero(), Chat()).ask("Pregunta")
    assert error.value.code == "invalid_embedding"


def test_protected_endpoint_answers_courses_even_if_model_would_abstain():
    secret = 'a-local-test-secret-with-at-least-32-chars'
    settings = Settings(_env_file=None, moodle_service_secret=secret)
    chat = Chat(GenerationOutput(answer='No sé', insufficient_context=True, source_ids=[]))
    queryservice = service(chat=chat)
    app = create_app(settings, repository=Repository(), query_service=queryservice)
    payload = {
        'query': 'qué cursos tengo?',
        'academic_context': {
            'courses': [{'course_id': 2, 'name': 'Algebra 101',
                         'short_name': 'ALG101', 'source': 'Moodle'}],
            'query': {'categories': ['courses'], 'course_mode': 'enrolled',
                      'assignment_filter': 'pending', 'has_more': False, 'complete': True,
                      'notices': [], 'document_question': ''},
        },
        'conversation_context': [{'question': 'cuánto pago?', 'answer': 'No hay información.'}],
    }
    body = json.dumps(payload).encode()
    response = TestClient(app).post('/api/v1/chat/query', content=body,
        headers=signed_moodle_headers(secret, body, courses=[2]))
    assert response.status_code == 200
    data = response.json()
    assert 'Algebra 101' in data['answer'] and 'Moodle' in data['answer']
    assert not data['insufficient_context'] and data['sources'] == []
    assert chat.calls == 0


def test_academic_results_distinguish_empty_errors_and_partial_answers():
    plan = {'categories': ['assignments'], 'assignment_filter': 'pending',
            'has_more': False, 'complete': True, 'document_question': '', 'notices': []}
    result = service().ask('tareas', academic_context={'query': plan, 'assignments': []})
    assert 'no tienes tareas pendientes' in result.answer and not result.insufficient_context
    with pytest.raises(AppError, match='datos académicos'):
        service().ask('tareas', academic_context={'query': plan, 'assignments': 'failed'})
    plan['notices'] = ['El asistente todavía no consulta pagos personales.']
    result = service().ask('tareas y pagos', academic_context={'query': plan, 'assignments': []})
    assert 'no tienes tareas pendientes' in result.answer and 'pagos personales' in result.answer


def test_mixed_answer_keeps_moodle_facts_separate_from_document_citations():
    context = {'courses': [{'name': 'Algebra 101', 'short_name': 'ALG101'}],
               'query': {'categories': ['courses'], 'document_question': 'nota mínima'}}
    result = service().ask('cursos y nota mínima', academic_context=context)
    academic, documentary = result.answer.split('Documentos:')
    assert 'Algebra 101' in academic and '[' not in academic
    assert '11' in documentary and '[1]' in documentary and len(result.sources) == 1


def test_new_signed_contract_does_not_allow_arbitrary_operations():
    with pytest.raises(ValidationError):
        QueryRequest(query='consulta', academic_context={'query': {'categories': ['payments']}})


def test_mixed_calendar_reports_a_clear_official_date_discrepancy():
    official = fragment() | {'tipo_documento': 'CALENDARIO',
                             'contenido': 'El ciclo inicia el 12 de agosto de 2026.'}
    chat = Chat(GenerationOutput(answer='El ciclo inicia el 12 de agosto de 2026. [1]',
                                insufficient_context=False, source_ids=[1]))
    context = {'calendar': [{'name': 'Inicio del ciclo', 'starts_date': '2026-09-01 08:00'}],
               'query': {'categories': ['calendar'], 'document_question': 'cuándo inicia el ciclo'}}
    result = service(Repository([official]), chat).ask('fecha del ciclo', academic_context=context)
    assert 'Discrepancia' in result.answer and '2026-09-01' in result.answer
    assert '2026-08-12' in result.answer and 'oficial tiene prioridad' in result.answer


def test_calendar_does_not_compare_different_exam_subjects():
    official = fragment() | {'tipo_documento': 'CALENDARIO',
                             'contenido': 'Examen de Matemáticas: 2026-12-01.'}
    chat = Chat(GenerationOutput(answer='Examen de Matemáticas: 2026-12-01. [1]',
                                insufficient_context=False, source_ids=[1]))
    context = {'calendar': [{'name': 'Examen de Biología', 'starts_date': '2026-11-01 08:00'}],
               'query': {'categories': ['calendar'], 'document_question': 'calendario'}}
    result = service(Repository([official]), chat).ask('calendario', academic_context=context)
    assert 'Discrepancia' not in result.answer and 'tiene prioridad' not in result.answer


def test_document_scope_cannot_exceed_signed_moodle_courses():
    secret = 'a-local-test-secret-with-at-least-32-chars'
    app = create_app(Settings(_env_file=None, moodle_service_secret=secret),
                     repository=Repository(), query_service=service())
    body = json.dumps({'query': 'documento', 'academic_context': {
        'query': {'categories': [], 'document_question': 'documento', 'document_course_ids': [99]}
    }}).encode()
    response = TestClient(app).post('/api/v1/chat/query', content=body,
        headers=signed_moodle_headers(secret, body, courses=[2]))
    assert response.status_code == 403


def test_document_failure_keeps_verified_academic_part_and_explains_failure():
    class UnavailableChat(Chat):
        def generate(self, *args, **kwargs):
            raise AppError('ollama_timeout', 'Modelo no disponible.')
    context = {'courses': [{'name': 'Algebra 101', 'short_name': 'ALG101'}],
               'query': {'categories': ['courses'], 'document_question': 'reglamento'}}
    result = service(chat=UnavailableChat()).ask('cursos y reglamento', academic_context=context)
    assert 'Algebra 101' in result.answer
    assert 'No pude consultar la parte documental' in result.answer
    assert not result.insufficient_context and not result.sources


def test_teacher_confirmation_is_direct_and_bounded_by_visible_data():
    secret = 'a-local-test-secret-with-at-least-32-chars'
    settings = Settings(_env_file=None, moodle_service_secret=secret)
    chat = Chat(GenerationOutput(
        answer='Diseño 204 — Carla Docente. [3]', insufficient_context=False, source_ids=[3]
    ))
    app = create_app(settings, repository=Repository(), query_service=service(chat=chat))
    payload = {
        'query': ('entonces la única docente que tengo registrado para este ciclo '
                  'es Carla Docente y nadie más?'),
        'academic_context': {
            'teachers': [
                {'course_id': 2, 'course_name': 'Algebra 101', 'names': [], 'state': 'ok'},
                {'course_id': 3, 'course_name': 'Biologia 102',
                 'names': ['Carla Docente'], 'state': 'ok'},
            ],
            'query': {'categories': ['teachers'], 'teacher_confirmation': True},
        },
    }
    body = json.dumps(payload).encode()
    response = TestClient(app).post('/api/v1/chat/query', content=body,
        headers=signed_moodle_headers(secret, body, courses=[2, 3]))
    assert response.status_code == 200
    answer = response.json()['answer']
    assert answer.startswith('Sí,')
    assert 'única docente visible' in answer
    assert 'No puedo asegurar' in answer and 'Algebra 101' in answer
    assert 'Docentes por curso' not in answer
    assert 'Diseño 204' not in answer and 'Calendario' not in answer
    assert response.json()['sources'] == [] and chat.calls == 0


@pytest.mark.parametrize("names,complete,has_more,expected", [
    (["Carla Docente", "Diego Profesor"], True, False, "No, además de Carla Docente"),
    (["Carla Docente"], False, False, "No puedo confirmar que sea la única"),
    (["Carla Docente"], True, True, "No puedo confirmar que sea la única"),
    ([], True, False, "No puedo confirmar quién te enseña"),
])
def test_teacher_confirmation_never_confuses_partial_or_empty_results_with_exclusivity(
    names, complete, has_more, expected,
):
    context = {
        'teachers': [{'course_name': 'Biologia 102', 'names': names, 'state': 'ok'}],
        'query': {'categories': ['teachers'], 'teacher_confirmation': True,
                  'complete': complete, 'has_more': has_more},
    }
    result = service().ask('¿Carla Docente es mi única docente?', academic_context=context)
    assert result.answer.startswith(expected)
    assert not result.sources
