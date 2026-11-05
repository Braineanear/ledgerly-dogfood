"""Tests for the /admin/stats route."""

from fastapi.testclient import TestClient

from ledgerly_api.admin import ADMIN_KEY
from ledgerly_api.main import create_app


def test_missing_key_returns_401_problem() -> None:
    """A missing X-Admin-Key header is rejected."""
    with TestClient(create_app()) as client:
        response = client.get("/admin/stats")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert "www-authenticate" not in response.headers


def test_missing_key_problem_details_payload() -> None:
    """A missing X-Admin-Key header yields RFC 9457 problem fields."""
    with TestClient(create_app()) as client:
        response = client.get("/admin/stats")

    data = response.json()
    assert data == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Missing or invalid admin key.",
        "instance": "/admin/stats",
    }


def test_wrong_key_returns_401_problem() -> None:
    """A wrong X-Admin-Key header is rejected."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/admin/stats", headers={"X-Admin-Key": "nope"}
        )

    assert response.status_code == 401
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert "www-authenticate" not in response.headers


def test_wrong_key_problem_details_payload() -> None:
    """A wrong X-Admin-Key header yields RFC 9457 problem fields."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/admin/stats", headers={"X-Admin-Key": "invalid-key"}
        )

    data = response.json()
    assert data == {
        "type": "about:blank",
        "title": "Unauthorized",
        "status": 401,
        "detail": "Missing or invalid admin key.",
        "instance": "/admin/stats",
    }


def test_correct_key_returns_200() -> None:
    """The correct X-Admin-Key header is accepted."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/admin/stats", headers={"X-Admin-Key": "dev-secret"}
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_admin_key_header_casing_variations() -> None:
    """Header names are case-insensitive per HTTP specifications."""
    with TestClient(create_app()) as client:
        resp_lower = client.get(
            "/admin/stats", headers={"x-admin-key": "dev-secret"}
        )
        resp_upper = client.get(
            "/admin/stats", headers={"X-ADMIN-KEY": "dev-secret"}
        )

    assert resp_lower.status_code == 200
    assert resp_lower.json() == {"status": "ok"}
    assert resp_upper.status_code == 200
    assert resp_upper.json() == {"status": "ok"}


def test_admin_key_value_case_sensitivity() -> None:
    """The key value comparison is case-sensitive."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/admin/stats", headers={"X-Admin-Key": "DEV-SECRET"}
        )

    assert response.status_code == 401


def test_admin_key_whitespace_and_empty_string() -> None:
    """Empty or whitespace-padded key values are rejected."""
    with TestClient(create_app()) as client:
        resp_empty = client.get(
            "/admin/stats", headers={"X-Admin-Key": ""}
        )
        resp_space = client.get(
            "/admin/stats", headers={"X-Admin-Key": " dev-secret "}
        )
        resp_newline = client.get(
            "/admin/stats", headers={"X-Admin-Key": "dev-secret\n"}
        )

    assert resp_empty.status_code == 401
    assert resp_space.status_code == 401
    assert resp_newline.status_code == 401


def test_admin_key_partial_and_extended_keys() -> None:
    """Prefixes, suffixes, and substrings of the key are rejected."""
    with TestClient(create_app()) as client:
        resp_prefix = client.get(
            "/admin/stats", headers={"X-Admin-Key": "dev-"}
        )
        resp_extended = client.get(
            "/admin/stats", headers={"X-Admin-Key": "dev-secret-extra"}
        )
        resp_suffix = client.get(
            "/admin/stats", headers={"X-Admin-Key": "secret"}
        )

    assert resp_prefix.status_code == 401
    assert resp_extended.status_code == 401
    assert resp_suffix.status_code == 401


def test_admin_stats_query_param_ignored() -> None:
    """Passing X-Admin-Key in query params is not accepted."""
    with TestClient(create_app()) as client:
        response = client.get("/admin/stats?X-Admin-Key=dev-secret")

    assert response.status_code == 401


def test_bearer_authorization_header_rejected() -> None:
    """Authorization Bearer header is ignored for admin route."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/admin/stats",
            headers={"Authorization": "Bearer dev-secret"},
        )

    assert response.status_code == 401
    assert "www-authenticate" not in response.headers


def test_admin_stats_unsupported_http_method() -> None:
    """Non-GET methods on /admin/stats return 405 Method Not Allowed."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/admin/stats", headers={"X-Admin-Key": "dev-secret"}
        )

    assert response.status_code == 405
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )


def test_module_admin_key_constant() -> None:
    """The module exports the expected hardcoded dev secret constant."""
    assert ADMIN_KEY == "dev-secret"
