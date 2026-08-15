from __future__ import annotations

import hashlib
import hmac


def sign_state(secret: str, token: str) -> str:
    signature = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    return f"{token}.{signature}"


def verify_state(secret: str, signed: str) -> str | None:
    try:
        token, signature = signed.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return token
