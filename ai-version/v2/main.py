"""Small auth API: FastAPI + Supabase Auth.

Run with:  python main.py   (listens on $PORT, default 8000)
Docs at:   http://localhost:8000/docs
"""

import sys

import uvicorn
from fastapi import Depends, FastAPI, Request, Response
from pydantic import BaseModel
from supabase import Client

from app.auth import CurrentUser, get_current_user, revoked_tokens
from app.config import settings
from app.errors import APIError, install_error_handlers
from app.rate_limit import LoginRateLimiter
from app.supabase_client import (
    SUPABASE_UNAVAILABLE,
    error_code,
    error_status,
    get_supabase,
    is_unavailable,
)

app = FastAPI(
    title="Auth API",
    description="FastAPI + Supabase Auth. Click **Authorize** and paste an access token.",
    version="2.0.0",
)
install_error_handlers(app)

login_limiter = LoginRateLimiter(
    max_failures=settings.login_max_failures,
    window_seconds=settings.login_window_seconds,
)

EMAIL_TAKEN_CODES = {"user_already_exists", "email_exists"}


# ---------------------------------------------------------------- schemas --
# Fields are optional on purpose: a missing field must give 400, not 422.
class Credentials(BaseModel):
    email: str | None = None
    password: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ErrorOut(BaseModel):
    error: str


class UserOut(BaseModel):
    id: str
    email: str | None
    created_at: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str


def _errors(*codes: int) -> dict:
    return {code: {"model": ErrorOut} for code in codes}


def _client_ip(request: Request) -> str:
    # Direct peer address. Behind a reverse proxy, run uvicorn with
    # --proxy-headers / forwarded_allow_ips so this reflects the real client.
    return request.client.host if request.client else "unknown"


def _tokens(session) -> TokensOut:
    if session is None or not session.access_token or not session.refresh_token:
        raise APIError(502, "Unexpected response from authentication service")
    return TokensOut(access_token=session.access_token, refresh_token=session.refresh_token)


# ------------------------------------------------------------------ auth --
@app.post(
    "/auth/signup",
    status_code=201,
    response_model=UserOut,
    tags=["auth"],
    responses=_errors(400, 409, 503),
)
def signup(body: Credentials | None = None, supabase: Client = Depends(get_supabase)):
    email = (body.email or "").strip() if body else ""
    password = body.password if body else None
    if not email or not password:
        raise APIError(400, "Email and password are required")

    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
    except Exception as exc:
        if is_unavailable(exc):
            raise APIError(503, SUPABASE_UNAVAILABLE)
        if error_code(exc) in EMAIL_TAKEN_CODES:
            raise APIError(409, "Email already registered")
        if error_status(exc) == 429:
            raise APIError(429, str(exc) or "Too many requests")
        # Weak password, invalid email, signups disabled, ...
        raise APIError(400, str(exc) or "Signup failed")

    user = result.user
    if user is None:
        raise APIError(502, "Unexpected response from authentication service")
    # With email confirmation on, Supabase hides "already registered" by
    # returning a fake user that has no identities.
    if user.identities is not None and len(user.identities) == 0:
        raise APIError(409, "Email already registered")

    # Only these three fields; never the full user object or any token.
    return UserOut(id=user.id, email=user.email, created_at=user.created_at.isoformat())


@app.post(
    "/auth/login",
    response_model=TokensOut,
    tags=["auth"],
    responses=_errors(400, 401, 429, 503),
)
def login(
    request: Request,
    body: Credentials | None = None,
    supabase: Client = Depends(get_supabase),
):
    email = (body.email or "").strip() if body else ""
    password = body.password if body else None
    if not email or not password:
        raise APIError(400, "Email and password are required")

    key = login_limiter.key(email, _client_ip(request))
    retry_after = login_limiter.retry_after(key)
    if retry_after is not None:
        # Refused locally; Supabase is not called.
        raise APIError(
            429,
            "Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        if is_unavailable(exc):
            raise APIError(503, SUPABASE_UNAVAILABLE)
        if error_status(exc) == 429:
            raise APIError(429, "Too many requests", headers={"Retry-After": "60"})
        login_limiter.record_failure(key)
        raise APIError(401, "Invalid login credentials")

    login_limiter.reset(key)
    return _tokens(result.session)


@app.post(
    "/auth/refresh",
    response_model=TokensOut,
    tags=["auth"],
    responses=_errors(400, 401, 503),
)
def refresh(body: RefreshRequest | None = None, supabase: Client = Depends(get_supabase)):
    refresh_token = (body.refresh_token or "").strip() if body else ""
    if not refresh_token:
        raise APIError(400, "refresh_token is required")

    try:
        result = supabase.auth.refresh_session(refresh_token)
    except Exception as exc:
        if is_unavailable(exc):
            raise APIError(503, SUPABASE_UNAVAILABLE)
        raise APIError(401, "Invalid or expired refresh token")

    return _tokens(result.session)


@app.post(
    "/auth/logout",
    status_code=204,
    response_class=Response,
    tags=["auth"],
    responses=_errors(401, 503),
)
def logout(
    user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        # Revokes the session this access token belongs to (and its
        # refresh token) on the Supabase side.
        supabase.auth.admin.sign_out(user.access_token, "local")
    except Exception as exc:
        if is_unavailable(exc):
            raise APIError(503, SUPABASE_UNAVAILABLE)
        # Session already gone: the token is no good either way.
        revoked_tokens.add(user.access_token)
        raise APIError(401, "Invalid or expired token")

    revoked_tokens.add(user.access_token)
    return Response(status_code=204)


# ---------------------------------------------------------------- public --
@app.get("/public/info", tags=["public"])
def public_info():
    return {"message": "Welcome stranger! This info is public."}


# ------------------------------------------------------------- protected --
@app.get(
    "/protected/profile",
    response_model=UserOut,
    tags=["protected"],
    responses=_errors(401, 503),
)
def profile(user: CurrentUser = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, created_at=user.created_at)


@app.get("/protected/dashboard", tags=["protected"], responses=_errors(401, 503))
def dashboard(user: CurrentUser = Depends(get_current_user)):
    return {
        "message": f"Welcome to your dashboard, {user.email}!",
        "user_id": user.id,
    }


@app.get("/protected/admin", tags=["protected"], responses=_errors(401, 403, 503))
def admin(user: CurrentUser = Depends(get_current_user)):
    if not user.email or user.email.lower() not in settings.admin_emails:
        raise APIError(403, "Admins only")
    return {"message": f"Welcome, admin {user.email}.", "user_id": user.id}


if __name__ == "__main__":
    missing = settings.missing()
    if missing:
        sys.exit(f"Missing required environment variables: {', '.join(missing)} (see .env.example)")
    uvicorn.run(app, host=settings.host, port=settings.port)
