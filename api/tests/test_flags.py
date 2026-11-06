"""Tests for GET /flags and the require_flag dependency."""

import secrets
from collections.abc import Iterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from ledgerly_shared.orm import Base, FeatureFlag
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ledgerly_api.auth import get_settings
from ledgerly_api.db import get_session
from ledgerly_api.flags import require_flag
from ledgerly_api.main import create_app

PROBLEM = "application/problem+json"
GENERATED = secrets.token_hex(16)
AUTH = {"Authorization": "Bearer " + GENERATED}


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("API_TOKEN", GENERATED)
    get_settings.cache_clear()
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()
    get_settings.cache_clear()


def _build_app(engine: Engine):
    def override_session() -> Iterator[Session]:
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_session] = override_session

    @application.get("/_beta", dependencies=[Depends(require_flag("beta"))])
    def beta() -> dict:
        return {"beta": True}

    return application


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with TestClient(_build_app(engine)) as test_client:
        yield test_client


def _seed(engine: Engine, **flags: bool) -> None:
    with Session(engine) as session:
        for name, enabled in flags.items():
            session.add(FeatureFlag(name=name, enabled=enabled))
        session.commit()


def test_enabled_flag_allows_route(client: TestClient, engine: Engine) -> None:
    _seed(engine, beta=True)

    response = client.get("/_beta")

    assert response.status_code == 200
    assert response.json() == {"beta": True}


def test_disabled_flag_returns_404_problem(
    client: TestClient, engine: Engine
) -> None:
    _seed(engine, beta=False)

    response = client.get("/_beta")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM
    assert response.json()["status"] == 404


def test_missing_flag_returns_404(client: TestClient) -> None:
    response = client.get("/_beta")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM


def test_database_error_is_not_a_404(engine: Engine) -> None:
    application = _build_app(engine)

    class BrokenSession(Session):
        def scalar(self, *args, **kwargs):
            raise OperationalError("SELECT", {}, Exception("database down"))

    def broken_session() -> Iterator[Session]:
        session = BrokenSession(engine)
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_session] = broken_session
    with TestClient(application, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_beta")

    assert response.status_code == 500


def test_list_flags_requires_token(client: TestClient) -> None:
    response = client.get("/flags")

    assert response.status_code == 401
    assert response.headers["content-type"] == PROBLEM


def test_list_flags_returns_seeded_flags(
    client: TestClient, engine: Engine
) -> None:
    _seed(engine, beta=True, alpha=False)

    response = client.get("/flags", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == [
        {"name": "alpha", "enabled": False},
        {"name": "beta", "enabled": True},
    ]
