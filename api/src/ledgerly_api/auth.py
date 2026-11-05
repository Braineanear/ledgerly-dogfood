"""Bearer-token authentication for the tenant routes."""

import os
import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Header, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from ledgerly_api.problems import problem_response


class Settings(BaseSettings):
    """Application settings read from the environment."""

    api_token: str
    database_url: str
    redis_url: str
    admin_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Build the settings on first use, never at import time."""
    return Settings()


def load_url_settings() -> Settings:
    """Build uncached settings so the URLs are read at call time.

    API_TOKEN is passed explicitly so reading the URLs never depends on it.
    """
    return Settings(api_token=os.environ.get("API_TOKEN", ""))


def validate_settings_at_startup() -> None:
    """Exit with one line naming each missing URL variable; ignore API_TOKEN."""
    missing: set[str] = set()
    try:
        Settings()
    except ValidationError as exc:
        missing = {
            error["loc"][0]
            for error in exc.errors()
            if error["type"] == "missing" and error["loc"]
        }
    names = []
    for name in ("database_url", "redis_url"):
        value = os.environ.get(name.upper())
        if name in missing or (value is not None and not value.strip()):
            names.append(name.upper())
    if names:
        raise SystemExit(
            "Missing required environment variable(s): " + ", ".join(names)
        ) from None


class AuthError(Exception):
    """Raised when a request lacks a valid bearer token."""

    def __init__(self, detail: str = "Missing or invalid bearer token.") -> None:
        super().__init__(detail)
        self.detail = detail


async def auth_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Render an AuthError as a 401 application/problem+json response."""
    detail = exc.detail if isinstance(exc, AuthError) else "Unauthorized."
    return problem_response(
        request,
        401,
        detail,
        title="Unauthorized",
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
