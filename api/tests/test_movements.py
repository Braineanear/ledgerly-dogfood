"""Tests for POST /tenants/{tenant_id}/movements and Idempotency-Key."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from ledgerly_shared.orm import Base, IdempotencyKey, StockMovement
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ledgerly_api.auth import get_settings
from ledgerly_api.db import get_session
from ledgerly_api.main import create_app

PROBLEM = "application/problem+json"
KEY = "Idempotency-Key"


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("API_TOKEN", "test-token")
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


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
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


def _make_tenant(client: TestClient, name: str) -> int:
    response = client.post("/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def _make_product(client: TestClient, tenant_id: int) -> dict:
    response = client.post(
        f"/tenants/{tenant_id}/products",
        json={
            "sku": "SKU-1",
            "name": "Widget",
            "price": 250,
            "currency": "USD",
        },
    )
    assert response.status_code == 201
    return response.json()


def _body(product_id: int, quantity: int = 5) -> dict:
    return {"product_id": product_id, "warehouse": "main", "quantity": quantity}


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_post_without_key_creates_movement(
    client: TestClient, engine: Engine
) -> None:
    tenant = _make_tenant(client, "A")
    product = _make_product(client, tenant)

    response = client.post(
        f"/tenants/{tenant}/movements", json=_body(product["id"])
    )

    assert response.status_code == 201
    data = response.json()
    assert data["product_id"] == product["id"]
    assert data["warehouse"] == "main"
    assert data["quantity"] == 5
    assert _count(engine, StockMovement) == 1
    assert _count(engine, IdempotencyKey) == 0


def test_replay_returns_first_response(
    client: TestClient, engine: Engine
) -> None:
    tenant = _make_tenant(client, "A")
    product = _make_product(client, tenant)
    url = f"/tenants/{tenant}/movements"

    first = client.post(url, json=_body(product["id"]), headers={KEY: "k1"})
    second = client.post(url, json=_body(product["id"]), headers={KEY: "k1"})

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert isinstance(second.json()["quantity"], int)
    assert _count(engine, StockMovement) == 1


def test_key_reuse_with_different_body_is_409(
    client: TestClient, engine: Engine
) -> None:
    tenant = _make_tenant(client, "A")
    product = _make_product(client, tenant)
    url = f"/tenants/{tenant}/movements"
    client.post(url, json=_body(product["id"], 5), headers={KEY: "k1"})

    response = client.post(
        url, json=_body(product["id"], 7), headers={KEY: "k1"}
    )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["status"] == 409
    assert _count(engine, StockMovement) == 1


def test_same_key_in_different_tenants_is_independent(
    client: TestClient, engine: Engine
) -> None:
    tenant_a = _make_tenant(client, "A")
    tenant_b = _make_tenant(client, "B")
    product_a = _make_product(client, tenant_a)
    product_b = _make_product(client, tenant_b)

    first = client.post(
        f"/tenants/{tenant_a}/movements",
        json=_body(product_a["id"]),
        headers={KEY: "shared"},
    )
    second = client.post(
        f"/tenants/{tenant_b}/movements",
        json=_body(product_b["id"]),
        headers={KEY: "shared"},
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert _count(engine, StockMovement) == 2
    assert _count(engine, IdempotencyKey) == 2


def test_post_without_token_is_401(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    product = _make_product(client, tenant)

    response = client.post(
        f"/tenants/{tenant}/movements",
        json=_body(product["id"]),
        headers={"Authorization": ""},
    )

    assert response.status_code == 401


def test_unknown_tenant_is_404_and_stores_no_key(
    client: TestClient, engine: Engine
) -> None:
    response = client.post(
        "/tenants/9999/movements", json=_body(1), headers={KEY: "k1"}
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert _count(engine, IdempotencyKey) == 0


def test_unknown_product_is_404_and_stores_no_key(
    client: TestClient, engine: Engine
) -> None:
    tenant = _make_tenant(client, "A")

    response = client.post(
        f"/tenants/{tenant}/movements", json=_body(999), headers={KEY: "k1"}
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert _count(engine, IdempotencyKey) == 0
    assert _count(engine, StockMovement) == 0
