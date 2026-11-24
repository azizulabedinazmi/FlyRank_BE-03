"""The guard. One dependency, reused by every protected route: `user: CurrentUser = Depends(current_user)`.

FastAPI runs it before the route body. If the token is missing or bad it raises a 401 and the route never runs.
"""
from dataclasses import dataclass

from fastapi import Header
from supabase_auth.errors import AuthApiError, AuthError

from errors import ApiError
from supabase_client import new_client

UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}  # tells the client which kind of credentials to send


@dataclass
class CurrentUser:
    id: str
    email: str | None
    created_at: str
    token: str  # kept so /auth/logout can end exactly this session


def extract_token(authorization: str | None) -> str:
    """Pull <token> out of 'Authorization: Bearer <token>'. Anything else is a 401."""
    scheme, _, token = (authorization or "").strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or " " in token:
        raise ApiError(401, "Access token required", UNAUTHORIZED)
    return token


def verify_token(token: str):
    """Ask Supabase whether this token is real. A network call, so the answer is trustworthy:
    expired, tampered-with, signed-out or made-up tokens all come back as an error."""
    try:
        res = new_client().auth.get_user(token)  # token is never empty here (see extract_token)
    except AuthApiError:
        raise ApiError(401, "Invalid or expired token", UNAUTHORIZED)
    except AuthError as e:
        raise ApiError(503, f"Could not reach Supabase: {e.__class__.__name__}")
    if res is None or res.user is None:
        raise ApiError(401, "Invalid or expired token", UNAUTHORIZED)
    return res.user


def current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    token = extract_token(authorization)
    user = verify_token(token)
    created = user.created_at
    return CurrentUser(id=user.id, email=user.email, token=token,
                       created_at=created.isoformat() if hasattr(created, "isoformat") else str(created))
