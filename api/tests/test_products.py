"""Tests for the product routes and tenant isolation."""

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

PROBLEM = "application/problem+json"


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


def test_owner_can_look_up_its_product(client: TestClient) -> None:
    tenant_a = _make_tenant(client, "A")
    product = _make_product(client, tenant_a)

    response = client.get(f"/tenants/{tenant_a}/products/{product['id']}")

    assert response.status_code == 200
    assert response.json() == product
    assert product["sku"] == "SKU-1"
    assert product["price"] == 250


def test_other_tenant_id_lookup_is_404_problem(client: TestClient) -> None:
    tenant_a = _make_tenant(client, "A")
    tenant_b = _make_tenant(client, "B")
    product = _make_product(client, tenant_a)

    response = client.get(f"/tenants/{tenant_b}/products/{product['id']}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["status"] == 404


def test_other_tenant_listing_excludes_product(client: TestClient) -> None:
    tenant_a = _make_tenant(client, "A")
    tenant_b = _make_tenant(client, "B")
    product = _make_product(client, tenant_a)

    listing_b = client.get(f"/tenants/{tenant_b}/products")
    listing_a = client.get(f"/tenants/{tenant_a}/products")

    assert listing_b.status_code == 200
    assert listing_b.json()["items"] == []
    assert listing_a.json()["items"] == [product]


def test_cross_tenant_404_matches_nonexistent_product(
    client: TestClient,
) -> None:
    tenant_a = _make_tenant(client, "A")
    tenant_b = _make_tenant(client, "B")
    product_id = _make_product(client, tenant_a)["id"]
    missing_id = product_id + 1000

    cross = client.get(f"/tenants/{tenant_b}/products/{product_id}")
    missing = client.get(f"/tenants/{tenant_b}/products/{missing_id}")

    assert cross.status_code == missing.status_code == 404
    assert cross.headers["content-type"].startswith(PROBLEM)
    assert missing.headers["content-type"].startswith(PROBLEM)
    assert cross.json()["detail"] == missing.json()["detail"].replace(
        str(missing_id), str(product_id)
    )
    assert cross.json()["title"] == missing.json()["title"]


def test_missing_tenant_is_404_problem(client: TestClient) -> None:
    response = client.get("/tenants/9999/products/1")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)


@pytest.mark.parametrize("product_id", [0, 2**63])
def test_out_of_range_product_id_is_422_problem(
    client: TestClient, product_id: int
) -> None:
    tenant_a = _make_tenant(client, "A")

    response = client.get(f"/tenants/{tenant_a}/products/{product_id}")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)
