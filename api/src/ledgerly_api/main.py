"""FastAPI application bootstrap."""

import os
import subprocess

from fastapi import FastAPI

from ledgerly_api.auth import AuthError, auth_error_handler
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


def create_app() -> FastAPI:
    """Create the Ledgerly API with health routes."""
    sha = resolve_git_sha()
    application = FastAPI(title="Ledgerly API")
    application.add_exception_handler(AuthError, auth_error_handler)
    application.include_router(tenants_router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/version")
    def health_version() -> dict[str, str]:
        return {"sha": sha}

    return application


app = create_app()
