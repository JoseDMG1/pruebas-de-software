"""Independent test helper for Moodle's documented HS256 request contract."""

import base64
import hashlib
import hmac
import json
import time


def signed_moodle_headers(secret, body, *, user_id="42", courses=None, expires_at=None):
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {
        "iss": "moodle",
        "aud": "rag-service",
        "sub": user_id,
        "courses": courses or [],
        "iat": now,
        "exp": expires_at or now + 60,
        "jti": "independent-test-id",
        "body_sha256": hashlib.sha256(body).hexdigest(),
    }

    def encode(value):
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    signing_input = f"{encode(header)}.{encode(claims)}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    token = f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
