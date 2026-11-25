"""The single reusable token check used by every protected route."""

import base64
import hashlib
import json
import threading
import time
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from .errors import APIError
from .supabase_client import SUPABASE_UNAVAILABLE, get_supabase, is_unavailable

# auto_error=False so a missing/invalid header produces our own JSON 401
# instead of FastAPI's default 403. Swagger still shows the Authorize button.
bearer_scheme = HTTPBearer(auto_error=False, description="Supabase access token")

TOKEN_REQUIRED = "Access token required"
TOKEN_INVALID = "Invalid or expired token"


class RevokedTokens:
    """Access tokens that were logged out through this API.

    Supabase's logout revokes the session (and its refresh tokens) and, on
    current Supabase Auth versions, GET /user then rejects access tokens tied
    to that session. This list is a second, local guarantee: a token we
    logged out is refused here even before asking Supabase. Entries are kept
    only until the token's own `exp`, and only hashes are stored.
    Like the rate limiter, it is per-process memory.
    """

    def __init__(self, clock=time.time) -> None:
        self._clock = clock
        self._entries: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _expiry(token: str, fallback: float) -> float:
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp")
            return float(exp) if exp else fallback
        except Exception:
            return fallback

    def add(self, token: str) -> None:
        now = self._clock()
        expires = self._expiry(token, fallback=now + 24 * 3600)
        with self._lock:
            self._purge(now)
            self._entries[self._digest(token)] = expires

    def contains(self, token: str) -> bool:
        with self._lock:
            self._purge(self._clock())
            return self._digest(token) in self._entries

    def _purge(self, now: float) -> None:
        for key in [k for k, exp in self._entries.items() if exp <= now]:
            del self._entries[key]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


revoked_tokens = RevokedTokens()


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    created_at: str
    access_token: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    supabase: Client = Depends(get_supabase),
) -> CurrentUser:
    token = credentials.credentials.strip() if credentials else ""
    if not token:
        raise APIError(401, TOKEN_REQUIRED)
    if revoked_tokens.contains(token):
        raise APIError(401, TOKEN_INVALID)

    try:
        response = supabase.auth.get_user(token)
    except Exception as exc:
        # Fail closed: if we cannot verify the token, nobody gets through.
        if is_unavailable(exc):
            raise APIError(503, SUPABASE_UNAVAILABLE)
        raise APIError(401, TOKEN_INVALID)

    user = getattr(response, "user", None)
    if user is None or not getattr(user, "id", None):
        raise APIError(401, TOKEN_INVALID)

    created_at = user.created_at
    return CurrentUser(
        id=user.id,
        email=user.email,
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
        access_token=token,
    )
