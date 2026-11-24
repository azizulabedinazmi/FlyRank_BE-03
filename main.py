import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field, StrictStr
from supabase_auth.errors import AuthApiError, AuthError

import errors
from errors import ApiError
from supabase_client import SUPABASE_URL, check_connection, new_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_connection()
    print(f"Server running and connected to Supabase ({SUPABASE_URL})", flush=True)
    yield


app = FastAPI(
    title="Auth API",
    version="1.0",
    description="Sign up, log in and log out with Supabase Auth, and protect routes with a bearer token.",
    lifespan=lifespan,
)
errors.install(app)


# ---------------------------------------------------------------------------- models
class Credentials(BaseModel):
    email: StrictStr | None = Field(default=None, examples=["test@example.com"])
    password: StrictStr | None = Field(default=None, examples=["password123"])


class UserOut(BaseModel):
    id: str
    email: str | None
    created_at: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: int | None
    user: UserOut


def require_credentials(body: Credentials) -> tuple[str, str]:
    """The server never trusts the client: both fields must be present and non-blank."""
    email = (body.email or "").strip()
    password = body.password or ""
    if not email or not password.strip():
        raise ApiError(400, "email and password are required")
    return email, password


def user_out(user) -> dict:
    """Only safe fields leave the server: no tokens, no app metadata, no identities."""
    created = user.created_at
    return {"id": user.id, "email": user.email,
            "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created)}


def supabase_down(exc: Exception) -> ApiError:
    return ApiError(503, f"Could not reach Supabase: {exc.__class__.__name__}")


# ---------------------------------------------------------------------------- auth
@app.post("/auth/signup", tags=["auth"], summary="Create a new user account", status_code=201,
          response_model=UserOut, responses=errors.responses(400, 409, 429, 503))
def signup(body: Credentials):
    email, password = require_credentials(body)
    try:
        res = new_client().auth.sign_up({"email": email, "password": password})
    except AuthApiError as e:
        if e.code in ("user_already_exists", "email_exists"):
            raise ApiError(409, "A user with this email already exists")
        if e.status == 429:
            raise ApiError(429, e.message)
        raise ApiError(400, e.message)  # weak password, invalid email format, signups disabled...
    except AuthError as e:
        raise supabase_down(e)
    return user_out(res.user)


@app.post("/auth/login", tags=["auth"], summary="Log in and get an access token (JWT)",
          response_model=TokensOut, responses=errors.responses(400, 401, 429, 503))
def login(body: Credentials):
    email, password = require_credentials(body)
    try:
        res = new_client().auth.sign_in_with_password({"email": email, "password": password})
    except AuthApiError as e:
        if e.status == 429:
            raise ApiError(429, e.message)
        if e.code == "email_not_confirmed":
            raise ApiError(401, "Email not confirmed")
        raise ApiError(401, "Invalid login credentials")
    except AuthError as e:
        raise supabase_down(e)
    s = res.session
    return {"access_token": s.access_token, "refresh_token": s.refresh_token, "token_type": "bearer",
            "expires_in": s.expires_in, "expires_at": s.expires_at, "user": user_out(res.user)}


# ---------------------------------------------------------------------------- public
@app.get("/public/info", tags=["public"], summary="Public info, no token needed")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


# ---------------------------------------------------------------------------- protected
UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}  # tells the client which kind of credentials to send


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
        raise supabase_down(e)
    if res is None or res.user is None:
        raise ApiError(401, "Invalid or expired token", UNAUTHORIZED)
    return res.user


@app.get("/protected/profile", tags=["protected"], summary="Your private profile",
         response_model=UserOut, responses=errors.responses(401, 503))
def profile(authorization: str | None = Header(default=None)):
    user = verify_token(extract_token(authorization))
    return user_out(user)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
