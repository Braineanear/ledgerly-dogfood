"""Tests for the tenant routes, using an in-memory SQLite database."""

from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from ledgerly_shared.orm import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ledgerly_api.auth import get_settings
from ledgerly_api.db import get_database_url, get_session
from ledgerly_api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    with TestClient(
        application, headers={"Authorization": "Bearer test-token"}
    ) as test_client:
        yield test_client
    engine.dispose()
    get_settings.cache_clear()


def test_post_creates_tenant_and_returns_id(client: TestClient) -> None:
    response = client.post("/tenants", json={"name": "Acme"})

    assert response.status_code == 201
    tenant_id = response.json()["id"]
    assert isinstance(tenant_id, int)
    fetched = client.get(f"/tenants/{tenant_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == tenant_id
    assert body["name"] == "Acme"
    assert isinstance(datetime.fromisoformat(body["created_at"]), datetime)


@pytest.mark.parametrize(
    "payload",
    [{}, {"name": ""}, {"name": "   "}, {"name": None}],
)
def test_post_rejects_missing_or_empty_name(client: TestClient, payload: dict) -> None:
    response = client.post("/tenants", json=payload)

    assert response.status_code == 422


def test_get_returns_tenant(client: TestClient) -> None:
    created = client.post("/tenants", json={"name": "  Globex  "}).json()

    response = client.get(f"/tenants/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Globex"
    assert isinstance(datetime.fromisoformat(body["created_at"]), datetime)


def test_get_unknown_tenant_returns_problem_json(client: TestClient) -> None:
    response = client.get("/tenants/999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert "999" in body["detail"]


def test_get_malformed_id_without_token_is_unauthorized(
    client: TestClient,
) -> None:
    del client.headers["Authorization"]

    response = client.get("/tenants/not-an-id")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"


def test_tests_are_isolated(client: TestClient) -> None:
    assert client.get("/tenants/1").status_code == 404


def test_database_url_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    assert get_database_url() == "sqlite://"
