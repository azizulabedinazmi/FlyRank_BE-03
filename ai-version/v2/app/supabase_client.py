"""A brand-new Supabase client per request, plus mapping of SDK errors.

Each request gets its own client with no persisted session and no auto
refresh, so one user's session can never leak into another request.
"""

from collections.abc import Iterator

import httpx
from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthApiError, AuthError, AuthRetryableError

from .config import settings
from .errors import APIError

SUPABASE_UNAVAILABLE = "Authentication service unavailable"


def get_supabase() -> Iterator[Client]:
    """FastAPI dependency: a fresh client for this request, closed afterwards.

    FastAPI caches a dependency per request, so a protected route and the
    token-check dependency share this one client, but no two requests do.
    """
    if settings.missing():
        raise APIError(503, SUPABASE_UNAVAILABLE)
    http_client = httpx.Client(timeout=settings.supabase_timeout)
    try:
        client = create_client(
            settings.supabase_url,
            settings.supabase_key,
            options=ClientOptions(
                persist_session=False,
                auto_refresh_token=False,
                httpx_client=http_client,
            ),
        )
    except Exception:
        http_client.close()
        raise APIError(503, SUPABASE_UNAVAILABLE)
    try:
        yield client
    finally:
        http_client.close()


def error_status(exc: Exception) -> int | None:
    """HTTP status Supabase answered with, or None if it never answered."""
    if isinstance(exc, AuthRetryableError):
        # status 0 = connection failure/timeout; 502/503/504 = gateway trouble.
        return None
    status = getattr(exc, "status", None)
    return status if isinstance(status, int) and status > 0 else None


def is_unavailable(exc: Exception) -> bool:
    """True when Supabase could not be reached or failed on its side.

    Anything that is not a clear 4xx answer from Supabase counts, so callers
    fail closed (503) instead of guessing.
    """
    if not isinstance(exc, AuthError):
        return True  # httpx errors, AuthUnknownError-like surprises, etc.
    status = error_status(exc)
    return status is None or status >= 500


def error_code(exc: Exception) -> str | None:
    return getattr(exc, "code", None)


__all__ = [
    "AuthApiError",
    "AuthError",
    "SUPABASE_UNAVAILABLE",
    "error_code",
    "error_status",
    "get_supabase",
    "is_unavailable",
]
