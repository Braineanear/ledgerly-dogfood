"""RFC 9457 problem details responses and the exception handlers. Part of Ledgerly."""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


def problem_response(
    request: Request,
    status: int,
    detail: str,
    title: str | None = None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an application/problem+json response for this request."""
    if title is None:
        try:
            title = HTTPStatus(status).phrase
        except ValueError:
            title = "Error"
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


class ForbiddenError(Exception):
    """Raised when a known caller lacks the role the route requires."""

    def __init__(self, detail: str = "Insufficient role for this tenant.") -> None:
        super().__init__(detail)
        self.detail = detail


async def forbidden_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render a ForbiddenError as a 403 application/problem+json response."""
    detail = exc.detail if isinstance(exc, ForbiddenError) else "Forbidden."
    return problem_response(request, 403, detail, title="Forbidden")


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render router and HTTP errors such as 404 and 405."""
    if not isinstance(exc, StarletteHTTPException):
        return await unhandled_exception_handler(request, exc)
    return problem_response(
        request,
        exc.status_code,
        str(exc.detail),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render request validation failures as 422 with field errors."""
    errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    return problem_response(
        request,
        422,
        "Request validation failed.",
        extra={"errors": jsonable_encoder(errors)},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log an unexpected error and answer a generic 500."""
    logger.error(
        "Unhandled exception for %s",
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return problem_response(request, 500, "Internal server error.")


def register_problem_handlers(app: FastAPI) -> None:
    """Register the problem+json handlers on the application."""
    app.add_exception_handler(ForbiddenError, forbidden_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
