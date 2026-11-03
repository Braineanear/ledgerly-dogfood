"""Smoke tests for the FastAPI application."""

import subprocess

import pytest
from fastapi.testclient import TestClient

from ledgerly_api import main
from ledgerly_api.main import app, create_app, resolve_git_sha


def test_create_app_returns_a_fastapi_application() -> None:
    """The placeholder application can be created without external services."""
    created_app = create_app()

    with TestClient(created_app) as client:
        response = client.get("/")

    assert response.status_code == 404


def test_module_application_is_available() -> None:
    """The documented ASGI import path exposes an application instance."""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 404


def test_health_returns_ok() -> None:
    """The health route reports ok."""
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_version_uses_env_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GIT_SHA takes precedence for the version route."""
    monkeypatch.setenv("GIT_SHA", "abc123")

    with TestClient(create_app()) as client:
        response = client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {"sha": "abc123"}


def test_sha_falls_back_to_unknown_when_git_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing git executable yields "unknown"."""
    monkeypatch.delenv("GIT_SHA", raising=False)

    def raise_missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(main.subprocess, "run", raise_missing)

    assert resolve_git_sha() == "unknown"
    with TestClient(create_app()) as client:
        assert client.get("/health/version").json() == {"sha": "unknown"}


def test_sha_is_read_from_git_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Git stdout is stripped and returned as a str."""
    monkeypatch.delenv("GIT_SHA", raising=False)

    def fake_run(*args: object, **kwargs: object):
        return subprocess.CompletedProcess(args, 0, stdout="deadbeef\n")

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    assert resolve_git_sha() == "deadbeef"


def test_sha_falls_back_when_git_has_no_stdout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Git with no captured output yields "unknown"."""
    monkeypatch.delenv("GIT_SHA", raising=False)

    def fake_run(*args: object, **kwargs: object):
        return subprocess.CompletedProcess(args, 0, stdout=None)

    monkeypatch.setattr(main.subprocess, "run", fake_run)

    assert resolve_git_sha() == "unknown"


def test_sha_is_resolved_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sha is resolved at app creation, not per request."""
    calls: list[int] = []

    def counting() -> str:
        calls.append(1)
        return "abc"

    monkeypatch.setattr(main, "resolve_git_sha", counting)

    with TestClient(create_app()) as client:
        client.get("/health/version")
        client.get("/health/version")

    assert len(calls) == 1
