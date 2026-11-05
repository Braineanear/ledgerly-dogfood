"""FastAPI application bootstrap."""

import os
import subprocess
from importlib.metadata import PackageNotFoundError, version
from time import monotonic

from fastapi import FastAPI

from ledgerly_api.admin import router as admin_router
from ledgerly_api.auth import (
    AuthError,
    auth_error_handler,
    validate_settings_at_startup,
)
from ledgerly_api.logging_config import configure_logging
from ledgerly_api.problems import register_problem_handlers
from ledgerly_api.products import router as products_router
from ledgerly_api.ready import router as ready_router
from ledgerly_api.request_id import RequestIdMiddleware
from ledgerly_api.tenants import router as tenants_router


def resolve_git_sha() -> str:
    """Return the git sha from GIT_SHA, then git, else "unknown"."""
    env_sha = os.environ.get("GIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            timeout=5,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (result.stdout or "").strip() or "unknown"


def resolve_package_version() -> str:
    """Return the ledgerly-api package version, else "unknown"."""
    try:
        return version("ledgerly-api")
    except PackageNotFoundError:
        return "unknown"


def create_app() -> FastAPI:
    """Create the Ledgerly API with health routes."""
    validate_settings_at_startup()
    configure_logging()
    sha = resolve_git_sha()
    started = monotonic()
    application = FastAPI(title="Ledgerly API")
    application.add_middleware(RequestIdMiddleware)
    application.add_exception_handler(AuthError, auth_error_handler)
    register_problem_handlers(application)
    application.include_router(tenants_router)
    application.include_router(products_router)
    application.include_router(ready_router)
    application.include_router(admin_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/version")
    def health_version() -> dict[str, str]:
        return {"sha": sha}

    @application.get("/version")
    def package_version() -> dict[str, str]:
        return {"version": resolve_package_version()}

    @application.get("/ping")
    def ping() -> dict[str, bool]:
        return {"pong": True}

    @application.get("/uptime")
    def uptime() -> dict[str, float]:
        return {"uptime_seconds": max(0.0, monotonic() - started)}

    return application


app = create_app()
