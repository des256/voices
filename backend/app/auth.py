"""Single-user session tokens: '<expiry>.<hmac>' signed with the server secret."""

from __future__ import annotations

import hashlib
import hmac

COOKIE_NAME = "voices_session"


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(secret: str, expires_at: int) -> str:
    payload = str(int(expires_at))
    return f"{payload}.{_sign(secret, payload)}"


def verify_token(secret: str, token: str | None, now: float) -> bool:
    if not token or "." not in token:
        return False
    payload, _, signature = token.partition(".")
    if not payload.isdigit():
        return False
    if not hmac.compare_digest(_sign(secret, payload), signature):
        return False
    return now < int(payload)
