"""Smoke tests for the FastAPI application."""

from fastapi.testclient import TestClient

from ledgerly_api.main import app, create_app


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
