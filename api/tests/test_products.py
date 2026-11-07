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
from ledgerly_api.products import _decode_cursor, _encode_cursor

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


def _add(client: TestClient, tenant_id: int, sku: str, name: str) -> None:
    response = client.post(
        f"/tenants/{tenant_id}/products",
        json={"sku": sku, "name": name, "price": 1, "currency": "USD"},
    )
    assert response.status_code == 201


def _names(client: TestClient, tenant_id: int, **params) -> list[str]:
    response = client.get(f"/tenants/{tenant_id}/products", params=params)
    assert response.status_code == 200
    return [item["name"] for item in response.json()["items"]]


def test_search_is_case_insensitive_substring(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    _add(client, tenant, "1", "Widget")
    _add(client, tenant, "2", "Big WIDGET")
    _add(client, tenant, "3", "Gadget")

    assert _names(client, tenant, q="wid") == ["Widget", "Big WIDGET"]
    assert _names(client, tenant, q="nomatch") == []


def test_search_wildcards_are_literal(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    _add(client, tenant, "1", "100% cotton")
    _add(client, tenant, "2", "a_b")
    _add(client, tenant, "3", "axb")

    assert _names(client, tenant, q="%") == ["100% cotton"]
    assert _names(client, tenant, q="a_b") == ["a_b"]


def test_search_backslash_is_literal(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    _add(client, tenant, "1", "a\\b")
    _add(client, tenant, "2", "a%b")
    _add(client, tenant, "3", "ab")

    assert _names(client, tenant, q="a\\b") == ["a\\b"]
    assert _names(client, tenant, q="\\") == ["a\\b"]


def test_search_is_tenant_scoped(client: TestClient) -> None:
    tenant_a = _make_tenant(client, "A")
    tenant_b = _make_tenant(client, "B")
    _add(client, tenant_a, "1", "Widget")

    assert _names(client, tenant_b, q="wid") == []
    assert _names(client, tenant_a, q="wid") == ["Widget"]


def test_search_paginates_with_cursor(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    for i in range(3):
        _add(client, tenant, f"W{i}", f"Widget {i}")
    _add(client, tenant, "G", "Gadget")

    seen: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"q": "widget", "limit": 1}
        if cursor:
            params["cursor"] = cursor
        body = client.get(f"/tenants/{tenant}/products", params=params).json()
        seen += [item["name"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert seen == ["Widget 0", "Widget 1", "Widget 2"]


def test_empty_search_returns_everything(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")
    _add(client, tenant, "1", "Widget")
    _add(client, tenant, "2", "Gadget")

    assert len(_names(client, tenant, q="")) == 2
    assert len(_names(client, tenant, q="   ")) == 2


def test_overlong_search_is_422_problem(client: TestClient) -> None:
    tenant = _make_tenant(client, "A")

    response = client.get(f"/tenants/{tenant}/products", params={"q": "x" * 256})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)


def test_cursor_from_other_tenant_decodes_to_none() -> None:
    cursor = _encode_cursor(1, 5)

    assert _decode_cursor(cursor, 1) == 5
    assert _decode_cursor(cursor, 2) is None
