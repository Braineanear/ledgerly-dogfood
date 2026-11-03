"""Tests for bearer-token authentication on the tenant routes."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from ledgerly_shared.orm import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ledgerly_api.auth import get_settings
from ledgerly_api.db import get_session
from ledgerly_api.main import create_app

TOKEN = "test-token"
GOOD = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_TOKEN", TOKEN)
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
    with TestClient(application) as test_client:
        yield test_client
    engine.dispose()
    get_settings.cache_clear()


def assert_unauthorized(response) -> None:
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Unauthorized"
    assert body["status"] == 401
    assert body["detail"]


def test_post_without_token_is_unauthorized(client: TestClient) -> None:
    assert_unauthorized(client.post("/tenants", json={"name": "Acme"}))


def test_get_without_token_is_unauthorized(client: TestClient) -> None:
    assert_unauthorized(client.get("/tenants/1"))


def test_wrong_token_is_unauthorized(client: TestClient) -> None:
    headers = {"Authorization": "Bearer nope"}

    assert_unauthorized(client.get("/tenants/1", headers=headers))


def test_non_bearer_scheme_is_unauthorized(client: TestClient) -> None:
    headers = {"Authorization": f"Basic {TOKEN}"}

    assert_unauthorized(client.get("/tenants/1", headers=headers))


def test_correct_token_creates_and_reads(client: TestClient) -> None:
    created = client.post("/tenants", json={"name": "Acme"}, headers=GOOD)

    assert created.status_code == 201
    fetched = client.get(f"/tenants/{created.json()['id']}", headers=GOOD)
    assert fetched.status_code == 200


def test_invalid_body_without_token_is_401_not_422(
    client: TestClient,
) -> None:
    assert_unauthorized(client.post("/tenants", json={}))


@pytest.mark.parametrize("value", [None, ""])
def test_unset_or_empty_api_token_fails_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("API_TOKEN", value)
    get_settings.cache_clear()

    assert_unauthorized(client.get("/tenants/1", headers=GOOD))


def test_health_routes_are_public(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/health/version").status_code == 200
