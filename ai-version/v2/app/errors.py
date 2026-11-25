"""JSON error responses: every error body is {"error": "..."} and never a 422."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


class APIError(Exception):
    def __init__(
        self, status_code: int, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.headers = dict(headers or {})
        if status_code == 401:
            self.headers.update(BEARER_CHALLENGE)


def error_response(
    status_code: int, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    headers = dict(headers or {})
    if status_code == 401:
        headers.update(BEARER_CHALLENGE)
    return JSONResponse(status_code=status_code, content={"error": message}, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return error_response(exc.status_code, exc.message, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Malformed JSON, wrong field types, etc. The spec forbids 422.
        return error_response(400, "Invalid request body")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = 400 if exc.status_code == 422 else exc.status_code
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return error_response(status, message, getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        return error_response(500, "Internal server error")
