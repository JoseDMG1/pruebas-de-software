"""Verification for signed, server-to-server Moodle chat requests."""

import base64
import hashlib
import hmac
import json
import re
import time
from typing import Any

from fastapi import HTTPException
from pydantic import SecretStr


MAX_ASSERTION_SECONDS = 120
CLOCK_SKEW_SECONDS = 30
MAX_COURSES = 500
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "invalid_moodle_assertion", "message": "Autenticación no válida."},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _decode_segment(segment: str) -> bytes:
    if not segment or not _BASE64URL.fullmatch(segment):
        raise _unauthorized()
    try:
        padded = segment + "=" * (-len(segment) % 4)
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (ValueError, base64.binascii.Error):
        raise _unauthorized() from None


def _decode_json(segment: str) -> dict[str, Any]:
    try:
        value = json.loads(_decode_segment(segment))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise _unauthorized() from None
    if not isinstance(value, dict):
        raise _unauthorized()
    return value


def verify_moodle_assertion(
    authorization: str | None,
    raw_body: bytes,
    secret: SecretStr | None,
    *,
    issuer: str = "moodle",
    audience: str = "rag-service",
    now: int | None = None,
) -> dict[str, Any]:
    """Verify assertion signature, lifetime, identity claims, and exact request body."""
    if secret is None or len(secret.get_secret_value()) < 32:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "moodle_auth_unavailable",
                "message": "Autenticación Moodle no configurada.",
            },
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    token = authorization.removeprefix("Bearer ")
    if len(token) > 8192:
        raise _unauthorized()
    parts = token.split(".")
    if len(parts) != 3:
        raise _unauthorized()
    encoded_header, encoded_claims, encoded_signature = parts
    header = _decode_json(encoded_header)
    claims = _decode_json(encoded_claims)
    if header != {"alg": "HS256", "typ": "JWT"}:
        raise _unauthorized()

    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    expected_signature = hmac.new(
        secret.get_secret_value().encode("utf-8"), signing_input, hashlib.sha256,
    ).digest()
    supplied_signature = _decode_segment(encoded_signature)
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise _unauthorized()

    current_time = int(time.time()) if now is None else now
    issued_at, expires_at = claims.get("iat"), claims.get("exp")
    user_id, courses = claims.get("sub"), claims.get("courses")
    jti, body_sha256 = claims.get("jti"), claims.get("body_sha256")
    if (
        claims.get("iss") != issuer
        or claims.get("aud") != audience
        or not isinstance(user_id, str)
        or not user_id.isascii()
        or not user_id.isdecimal()
        or int(user_id) <= 0
        or type(issued_at) is not int
        or type(expires_at) is not int
        or issued_at > current_time + CLOCK_SKEW_SECONDS
        or expires_at <= current_time
        or expires_at <= issued_at
        or expires_at - issued_at > MAX_ASSERTION_SECONDS
        or not isinstance(jti, str)
        or not 1 <= len(jti) <= 128
        or not isinstance(body_sha256, str)
        or not hmac.compare_digest(body_sha256, hashlib.sha256(raw_body).hexdigest())
        or not isinstance(courses, list)
        or len(courses) > MAX_COURSES
        or any(type(course_id) is not int or course_id <= 0 for course_id in courses)
        or len(set(courses)) != len(courses)
    ):
        raise _unauthorized()

    return claims
