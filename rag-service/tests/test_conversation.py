import json

from fastapi.testclient import TestClient

from moodle_auth_support import signed_moodle_headers
from rag_service.api import create_app
from rag_service.config import Settings

SECRET = 'a-conversation-test-secret-with-at-least-32-chars'


class Interpreter:
    calls = 0

    def interpret(self, request):
        self.calls += 1
        return {'intent': 'social', 'social': 'greeting', 'categories': []}


def client(interpreter=None):
    return TestClient(create_app(
        Settings(_env_file=None, moodle_service_secret=SECRET),
        repository=object(), query_service=interpreter or Interpreter(),
    ))


def payload():
    return {'query': 'hola como estás', 'conversation_context': [],
            'runtime': {'now': 1791208800, 'timezone': 'America/Lima'}}


def post(app, data, path='/api/v1/chat/interpret'):
    body = json.dumps(data).encode()
    return app.post(path, content=body, headers=signed_moodle_headers(SECRET, body))


def test_interpretation_is_signed_and_does_not_accept_identity_from_input():
    interpreter = Interpreter()
    app = client(interpreter)
    data = payload()
    assert app.post('/api/v1/chat/interpret', json=data).status_code == 401
    response = post(app, data)
    assert response.status_code == 200
    assert response.json()['intent'] == 'social'
    assert response.json()['categories'] == []
    assert interpreter.calls == 1
    assert post(app, data | {'user_id': 2}).status_code == 422
    invalid_clock = data | {'runtime': {'now': 1791208800, 'timezone': 'Invalid/Zone'}}
    assert post(app, invalid_clock).status_code == 422


def test_invalid_interpretation_does_not_become_a_read_operation():
    class Invalid(Interpreter):
        def interpret(self, request):
            return {'intent': 'academic', 'categories': ['sql'], 'user_id': 99}
    response = post(client(Invalid()), payload())
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'interpretation_unavailable'
