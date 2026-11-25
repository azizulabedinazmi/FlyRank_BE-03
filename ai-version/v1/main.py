"""Small auth API: FastAPI + Supabase Auth.

Run with either:
    python main.py
    uvicorn main:app --port 8000
"""

import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import (
    AuthApiError,
    AuthError,
    AuthRetryableError,
    Client,
    ClientOptions,
    create_client,
)
from supabase_auth.types import User

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set (copy .env.example to .env)."
    )


def new_supabase_client() -> Client:
    """Create a Supabase client that keeps no session around.

    sign_up / sign_in_with_password store the resulting session inside the
    client object. A shared, module-level client would therefore leak one
    user's session into other requests, so those calls get a fresh client.
    """
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


# Shared client for stateless calls only (get_user(jwt), admin.sign_out(jwt)):
# both pass the user's token explicitly and do not touch stored session state.
supabase: Client = new_supabase_client()

app = FastAPI(title="Auth API", version="1.0.0")

# auto_error=False so a missing header reaches our dependency and we can
# return our own {"error": ...} body instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


# --------------------------------------------------------------------------
# Error handling: every error response is {"error": "..."}
# --------------------------------------------------------------------------


class APIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


@app.exception_handler(APIError)
async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code, content={"error": message}, headers=exc.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    # Malformed / non-JSON bodies end up here; treat as a bad request.
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(p) for p in first.get("loc", []) if p != "body")
    message = first.get("msg", "Invalid request")
    if location:
        message = f"{location}: {message}"
    return JSONResponse(status_code=400, content={"error": message})


# --------------------------------------------------------------------------
# Auth dependency (used by every protected route)
# --------------------------------------------------------------------------


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None or not credentials.credentials:
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Access token required")

    try:
        response = supabase.auth.get_user(credentials.credentials)
    except AuthRetryableError:
        # Network problem talking to Supabase - not the caller's fault.
        raise APIError(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
    except AuthError:
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if response is None or response.user is None:
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return response.user


def get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    return credentials.credentials if credentials else None


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class Credentials(BaseModel):
    # Optional so that a missing field is reported as our 400, not a 422.
    email: str | None = None
    password: str | None = None


def require_credentials(body: Credentials) -> tuple[str, str]:
    email = (body.email or "").strip()
    password = body.password or ""
    if not email or not password:
        raise APIError(status.HTTP_400_BAD_REQUEST, "Email and password are required")
    return email, password


def user_to_dict(user: User) -> dict:
    return user.model_dump(mode="json")


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, tags=["auth"])
def signup(body: Credentials):
    email, password = require_credentials(body)
    try:
        result = new_supabase_client().auth.sign_up(
            {"email": email, "password": password}
        )
    except AuthRetryableError:
        raise APIError(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
    except AuthError as exc:
        # e.g. "User already registered", weak password, invalid email.
        code = getattr(exc, "status", None) or 400
        if code >= 500:
            code = 502
        raise APIError(code, exc.message)

    if result.user is None:
        raise APIError(status.HTTP_400_BAD_REQUEST, "Signup failed")
    # If email confirmation is enabled in Supabase, no session is issued yet;
    # the user must confirm their email before logging in.
    return {"user": user_to_dict(result.user)}


@app.post("/auth/login", tags=["auth"])
def login(body: Credentials):
    email, password = require_credentials(body)
    try:
        result = new_supabase_client().auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except AuthRetryableError:
        raise APIError(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
    except AuthApiError as exc:
        if exc.status >= 500:
            raise APIError(status.HTTP_502_BAD_GATEWAY, "Auth service error")
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Invalid login credentials")
    except AuthError:
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Invalid login credentials")

    session = result.session
    if session is None:
        raise APIError(status.HTTP_401_UNAUTHORIZED, "Invalid login credentials")
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "bearer",
        "expires_in": session.expires_in,
    }


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
def logout(
    _user: User = Depends(get_current_user),
    token: str | None = Depends(get_token),
):
    # The anon-key client has no server-side session for this user, so we
    # revoke the session that owns this token directly. scope="local" ends
    # only this session; use "global" to sign the user out everywhere.
    # Note: the refresh token is revoked, but the access token (a JWT) stays
    # valid until it expires - that is how Supabase Auth works.
    try:
        supabase.auth.admin.sign_out(token, scope="local")
    except AuthApiError as exc:
        if exc.status not in (401, 403, 404):  # already signed out is fine
            raise APIError(status.HTTP_502_BAD_GATEWAY, "Logout failed")
    except AuthError:
        raise APIError(status.HTTP_503_SERVICE_UNAVAILABLE, "Auth service unavailable")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Public route
# --------------------------------------------------------------------------


@app.get("/public/info", tags=["public"])
def public_info():
    return {"message": "Welcome stranger! This info is public."}


# --------------------------------------------------------------------------
# Protected routes
# --------------------------------------------------------------------------


@app.get("/protected/profile", tags=["protected"])
def profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
    }


@app.get("/protected/dashboard", tags=["protected"])
def dashboard(user: User = Depends(get_current_user)):
    return {
        "message": f"Welcome to your dashboard, {user.email}!",
        "user_id": user.id,
        "last_sign_in_at": user.last_sign_in_at,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
