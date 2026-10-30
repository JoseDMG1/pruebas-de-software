import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request

import httpx
import pytest

from rag_service import provider_http


def test_connections_are_reused_without_sharing_request_credentials(monkeypatch):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            seen.append((self.client_address[1], self.headers.get('Authorization'), body))
            result = b'{"ok":true}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(result)))
            self.end_headers()
            self.wfile.write(result)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(trust_env=False) as client:
            monkeypatch.setattr(provider_http, '_client', client)
            url = f'http://127.0.0.1:{server.server_port}/test'
            first = Request(url, data=b'first', headers={'Authorization': 'Bearer test-only'})
            second = Request(url, data=b'second')
            for request in [first, second]:
                with provider_http.urlopen(request, timeout=120) as response:
                    assert json.load(response) == {'ok': True}
        assert seen[0][0] == seen[1][0], 'Each call opened a new TCP connection'
        assert seen[0][1] == 'Bearer test-only' and seen[1][1] is None
        assert [x[2] for x in seen] == [b'first', b'second']
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_separate_connect_and_read_timeouts_and_http_errors(monkeypatch):
    def handler(request):
        assert request.extensions['timeout']['connect'] == 3
        assert request.extensions['timeout']['read'] == 120
        return httpx.Response(429, json={'error': 'limited'})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(provider_http, '_client', client)
        with pytest.raises(HTTPError) as error:
            with provider_http.urlopen(Request('https://example.test', data=b'{}'), timeout=120):
                pass
        assert error.value.code == 429
        assert json.load(error.value) == {'error': 'limited'}


@pytest.mark.parametrize('error,expected', [
    (httpx.ConnectTimeout('sensitive'), TimeoutError),
    (httpx.ReadTimeout('sensitive'), TimeoutError),
    (httpx.ConnectError('sensitive'), URLError),
])
def test_transport_errors_preserve_safe_retry_contract(monkeypatch, error, expected):
    def handler(request):
        raise error

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(provider_http, '_client', client)
        with pytest.raises(expected) as caught:
            with provider_http.urlopen(Request('https://example.test', data=b'{}'), timeout=120):
                pass
        assert 'sensitive' not in str(caught.value)
