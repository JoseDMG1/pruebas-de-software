"""Reusable provider connections with bounded establishment time.

Preserves the small urllib-shaped interface used by provider adapters and tests.
Only network connections are reused: responses, prompts and authorization decisions
are never cached. Credentials are attached to each request, not to the client.
"""
import atexit
from contextlib import contextmanager
from io import BytesIO
from urllib.error import HTTPError, URLError

import httpx

_client = httpx.Client(
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=20, keepalive_expiry=60),
    follow_redirects=False,
)
atexit.register(_client.close)


@contextmanager
def urlopen(request, timeout):
    try:
        response = _client.request(
            request.get_method(),
            request.full_url,
            headers=dict(request.header_items()),
            content=request.data,
            timeout=httpx.Timeout(timeout, connect=min(3, timeout), pool=min(3, timeout)),
        )
    except httpx.TimeoutException as exc:
        raise TimeoutError('Provider connection or response timed out.') from exc
    except httpx.RequestError as exc:
        raise URLError('Provider transport unavailable.') from exc
    try:
        if not 200 <= response.status_code < 300:
            raise HTTPError(
                request.full_url, response.status_code, 'Provider HTTP error',
                dict(response.headers), BytesIO(response.content),
            )
        yield response
    finally:
        response.close()
