"""Tests for the X-Admin-Key guard on /admin/stats."""

import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ledgerly_api.auth import get_settings
from ledgerly_api.main import create_app

ENV_NAME = "ADMIN_KEY"
HEADER = "X-Admin-Key"


@pytest.fixture(autouse=True)
def api_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings requires API_TOKEN, so give it a generated value."""
    monkeypatch.setenv("API_TOKEN", secrets.token_hex(16))


@pytest.fixture
def client(api_token: None) -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def assert_unauthorized(response) -> None:
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert "www-authenticate" not in response.headers
    body = response.json()
    assert body["status"] == 401
    assert body["title"] == "Unauthorized"
    assert body["detail"]


def test_missing_key_header_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_NAME, secrets.token_hex(16))
    get_settings.cache_clear()

    assert_unauthorized(client.get("/admin/stats"))


def test_wrong_key_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    other = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: other})

    assert_unauthorized(response)


def test_empty_key_header_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_NAME, secrets.token_hex(16))
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: ""})

    assert_unauthorized(response)


def test_compose_forwards_admin_key_to_api_service() -> None:
    compose = Path(__file__).resolve().parents[2] / "compose.yaml"
    block = []
    in_api = False
    for line in compose.read_text().splitlines():
        if line.startswith("  ") and not line.startswith("   "):
            in_api = line.strip() == "api:"
        if in_api:
            block.append(line.strip())

    assert "ADMIN_KEY: ${ADMIN_KEY:-}" in block


def test_bearer_authorization_alone_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer " + value}

    assert_unauthorized(client.get("/admin/stats", headers=headers))


@pytest.mark.parametrize("configured", [None, ""])
def test_unset_or_empty_admin_key_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
) -> None:
    if configured is None:
        monkeypatch.delenv(ENV_NAME, raising=False)
    else:
        monkeypatch.setenv(ENV_NAME, configured)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: ""})

    assert_unauthorized(response)


def test_correct_key_returns_ok(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: value})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("configured", [None, ""])
def test_unset_or_empty_admin_key_fails_closed_with_supplied_header(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
) -> None:
    if configured is None:
        monkeypatch.delenv(ENV_NAME, raising=False)
    else:
        monkeypatch.setenv(ENV_NAME, configured)
    get_settings.cache_clear()

    tok = secrets.token_hex(16)
    response = client.get("/admin/stats", headers={HEADER: tok})

    assert_unauthorized(response)


@pytest.mark.parametrize("whitespace_val", ["   ", "\t\n", " "])
def test_whitespace_only_admin_key_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    whitespace_val: str,
) -> None:
    monkeypatch.setenv(ENV_NAME, whitespace_val)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: whitespace_val})

    assert_unauthorized(response)


@pytest.mark.parametrize("header_name", ["x-admin-key", "X-ADMIN-KEY", "X-Admin-Key"])
def test_header_case_insensitivity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    header_name: str,
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={header_name: value})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_non_ascii_key_header_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_NAME, secrets.token_hex(16))
    get_settings.cache_clear()
    raw = "admin-val-\u00e9".encode("latin-1")

    response = client.get("/admin/stats", headers={HEADER: raw})

    assert_unauthorized(response)


def test_key_with_leading_or_trailing_whitespace_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    response = client.get("/admin/stats", headers={HEADER: f" {value} "})

    assert_unauthorized(response)


def test_invalid_http_methods_on_admin_stats(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    response = client.post("/admin/stats", headers={HEADER: value})

    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"


def test_partial_key_match_is_unauthorized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = secrets.token_hex(16)
    monkeypatch.setenv(ENV_NAME, value)
    get_settings.cache_clear()

    assert_unauthorized(client.get("/admin/stats", headers={HEADER: value[:-1]}))
    assert_unauthorized(client.get("/admin/stats", headers={HEADER: value + "x"}))

