"""Every error this API sends looks the same: a status code and {"error": "..."}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class Error(BaseModel):
    error: str


class ApiError(Exception):
    def __init__(self, status: int, message: str, headers: dict | None = None):
        self.status, self.message, self.headers = status, message, headers


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    def api_error(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"error": exc.message}, headers=exc.headers)

    # FastAPI answers bad input with 422 by default; this API uses 400 + {"error": ...} like the earlier assignments.
    @app.exception_handler(RequestValidationError)
    def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0]
        field = ".".join(str(p) for p in first["loc"] if isinstance(p, str) and p != "body")
        return JSONResponse(status_code=400, content={"error": f"Invalid {field or 'body'}: {first['msg']}"})


def responses(*codes: int) -> dict:
    """OpenAPI docs for the error codes a route can return."""
    text = {400: "Missing or invalid input", 401: "Missing, invalid or expired token", 403: "Not allowed",
            409: "Already exists", 429: "Too many attempts", 503: "Supabase unreachable"}
    return {c: {"model": Error, "description": text[c]} for c in codes}
