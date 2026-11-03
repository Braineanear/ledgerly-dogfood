"""Bearer-token authentication for the tenant routes."""

import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings read from the environment."""

    api_token: str


@lru_cache
def get_settings() -> Settings:
    """Build the settings on first use, never at import time."""
    return Settings()


class AuthError(Exception):
    """Raised when a request lacks a valid bearer token."""

    def __init__(self, detail: str = "Missing or invalid bearer token.") -> None:
        super().__init__(detail)
        self.detail = detail


async def auth_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render an AuthError as a 401 application/problem+json response."""
    detail = exc.detail if isinstance(exc, AuthError) else "Unauthorized."
    return JSONResponse(
        status_code=401,
        content={
            "type": "about:blank",
            "title": "Unauthorized",
            "status": 401,
            "detail": detail,
        },
        media_type="application/problem+json",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _parse_bearer(authorization: str | None) -> str:
    if not authorization:
        raise AuthError("Missing Authorization header.")
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise AuthError("Authorization header must be 'Bearer <token>'.")
    return token


def require_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Require ``Authorization: Bearer <API_TOKEN>``; fail closed."""
    token = _parse_bearer(authorization)
    try:
        expected = get_settings().api_token
    except ValidationError:
        raise AuthError() from None
    if not expected:
        raise AuthError()
    if not secrets.compare_digest(token.encode(), expected.encode()):
        raise AuthError()
