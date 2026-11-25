"""The guard. One dependency, reused by every protected route: `user: CurrentUser = Depends(current_user)`.

FastAPI runs it before the route body. If the token is missing or bad it raises a 401 and the route never runs.
"""
from dataclasses import dataclass

import os

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


# HTTPBearer is what puts the "Authorize" padlock in Swagger UI and marks routes that use it as locked.
# auto_error=False: it hands us None instead of raising its own 403, so every failure uses our 401 + JSON shape.
bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth", bearerFormat="JWT",
                    description="Paste the access_token from POST /auth/login (without the word Bearer).")


def extract_token(creds: HTTPAuthorizationCredentials | None) -> str:
    """HTTPBearer already split 'Authorization: Bearer <token>'. It returns None when the header is missing or
    isn't Bearer. We still reject an empty token or one with spaces ('Bearer a b')."""
    token = creds.credentials.strip() if creds else ""
    if not token or " " in token:
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


def current_user(creds: HTTPAuthorizationCredentials | None = Security(bearer)) -> CurrentUser:
    token = extract_token(creds)
    user = verify_token(token)
    created = user.created_at
    return CurrentUser(id=user.id, email=user.email, token=token,
                       created_at=created.isoformat() if hasattr(created, "isoformat") else str(created))


# Authorization on top of authentication: the same guard first proves who you are, then this checks what you may do.
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if (user.email or "").lower() not in ADMIN_EMAILS:
        raise ApiError(403, "Admins only")
    return user
