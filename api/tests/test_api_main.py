"""Smoke tests for the FastAPI application."""

import subprocess
from importlib import metadata

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


def test_ping_returns_pong() -> None:
    """The ping route reports pong."""
    with TestClient(create_app()) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert response.json() == {"pong": True}


def test_ping_disallows_post() -> None:
    """POST on /ping returns 405 Method Not Allowed."""
    with TestClient(create_app()) as client:
        response = client.post("/ping")

    assert response.status_code == 405


def test_health_version_uses_env_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GIT_SHA takes precedence for the version route."""
    monkeypatch.setenv("GIT_SHA", "abc123")

    with TestClient(create_app()) as client:
        response = client.get("/health/version")

    assert response.status_code == 200
    assert response.json() == {"sha": "abc123"}


def test_version_returns_package_version() -> None:
    """The version route reports the installed api package version."""
    with TestClient(create_app()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": metadata.version("ledgerly-api")}


def test_version_falls_back_to_unknown_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing distribution yields "unknown"."""

    def raise_missing(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(main, "version", raise_missing)

    with TestClient(create_app()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "unknown"}


def test_health_version_keeps_sha_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The existing health version route still returns the sha."""
    monkeypatch.setenv("GIT_SHA", "abc123")

    with TestClient(create_app()) as client:
        response = client.get("/health/version")

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


def test_version_returns_json_content_type() -> None:
    """The version route returns application/json content-type header."""
    with TestClient(create_app()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_version_disallows_non_get_methods(method: str) -> None:
    """Non-GET HTTP methods on /version return 405 Method Not Allowed."""
    with TestClient(create_app()) as client:
        client_method = getattr(client, method)
        response = client_method("/version")

    assert response.status_code == 405


def test_version_ignores_query_parameters() -> None:
    """The version endpoint ignores arbitrary query parameters."""
    with TestClient(create_app()) as client:
        response = client.get("/version?debug=true&format=raw")

    assert response.status_code == 200
    assert "version" in response.json()


def test_version_is_public_with_or_without_auth_headers() -> None:
    """The version route accepts requests regardless of authorization headers."""
    with TestClient(create_app()) as client:
        res_no_auth = client.get("/version")
        res_bad_auth = client.get(
            "/version", headers={"Authorization": "Bearer invalid-token"}
        )

    assert res_no_auth.status_code == 200
    assert res_bad_auth.status_code == 200
    assert res_no_auth.json() == res_bad_auth.json()


def test_version_response_includes_request_id_header() -> None:
    """The version response includes the x-request-id middleware header."""
    with TestClient(create_app()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_version_returns_custom_package_version_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The version route passes through any package version string verbatim."""
    monkeypatch.setattr(main, "version", lambda name: "1.2.3-beta.4")

    with TestClient(create_app()) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "1.2.3-beta.4"}


def _fake_clock(monkeypatch: pytest.MonkeyPatch, times: list[float]) -> None:
    """Replace main.monotonic with a clock that yields times in order."""
    values = iter(times)
    monkeypatch.setattr(main, "monotonic", lambda: next(values))


def test_uptime_returns_seconds_since_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime route reports the time elapsed since app creation."""
    _fake_clock(monkeypatch, [100.0, 107.5])

    with TestClient(create_app()) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    assert response.json() == {"uptime_seconds": 7.5}


def test_uptime_increases_between_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later request reports a larger uptime than an earlier one."""
    _fake_clock(monkeypatch, [100.0, 101.0, 105.0])

    with TestClient(create_app()) as client:
        first = client.get("/uptime").json()["uptime_seconds"]
        second = client.get("/uptime").json()["uptime_seconds"]

    assert first == 1.0
    assert second == 5.0
    assert second > first


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_uptime_disallows_non_get_methods(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """Non-GET HTTP methods on /uptime return 405 Method Not Allowed."""
    _fake_clock(monkeypatch, [100.0, 101.0])

    with TestClient(create_app()) as client:
        response = getattr(client, method)("/uptime")

    assert response.status_code == 405


def test_uptime_is_public_with_bad_auth_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime route ignores an invalid authorization header."""
    _fake_clock(monkeypatch, [100.0, 107.5])

    with TestClient(create_app()) as client:
        response = client.get(
            "/uptime", headers={"Authorization": "Bearer invalid-token"}
        )

    assert response.status_code == 200
    assert response.json() == {"uptime_seconds": 7.5}


def test_uptime_response_includes_request_id_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime response includes the x-request-id middleware header."""
    _fake_clock(monkeypatch, [100.0, 107.5])

    with TestClient(create_app()) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_uptime_zero_elapsed_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uptime returns 0.0 when no time has elapsed since app creation."""
    _fake_clock(monkeypatch, [500.0, 500.0])

    with TestClient(create_app()) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    assert response.json() == {"uptime_seconds": 0.0}


def test_uptime_clamped_to_zero_on_backward_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uptime is non-negative even if monotonic time moves backward."""
    _fake_clock(monkeypatch, [500.0, 450.0])

    with TestClient(create_app()) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    assert response.json() == {"uptime_seconds": 0.0}


def test_uptime_content_type_is_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime route returns application/json content-type header."""
    _fake_clock(monkeypatch, [100.0, 105.0])

    with TestClient(create_app()) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


def test_uptime_ignores_query_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime endpoint ignores arbitrary query parameters."""
    _fake_clock(monkeypatch, [100.0, 102.5])

    with TestClient(create_app()) as client:
        response = client.get("/uptime?debug=true&foo=bar")

    assert response.status_code == 200
    assert response.json() == {"uptime_seconds": 2.5}


def test_uptime_module_app_instance() -> None:
    """The module-level app instance responds to GET /uptime."""
    with TestClient(app) as client:
        response = client.get("/uptime")

    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0.0


def test_uptime_independent_per_app_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separate app instances track independent start times."""
    _fake_clock(monkeypatch, [100.0, 200.0, 210.0, 215.0])

    app1 = create_app()
    app2 = create_app()

    with TestClient(app1) as client1, TestClient(app2) as client2:
        res1 = client1.get("/uptime")
        res2 = client2.get("/uptime")

    assert res1.json() == {"uptime_seconds": 110.0}
    assert res2.json() == {"uptime_seconds": 15.0}


def test_uptime_response_exact_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The uptime JSON object contains exactly the 'uptime_seconds' key."""
    _fake_clock(monkeypatch, [100.0, 105.0])

    with TestClient(create_app()) as client:
        data = client.get("/uptime").json()

    assert list(data.keys()) == ["uptime_seconds"]


