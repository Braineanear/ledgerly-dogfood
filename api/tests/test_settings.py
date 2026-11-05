"""Tests for the fail-fast startup validation of required settings."""

import pytest
from fastapi.testclient import TestClient

from ledgerly_api.auth import get_settings, validate_settings_at_startup
from ledgerly_api.main import create_app

DB_VALUE = "postgresql://ledger:hunter2@db.internal/ledgerly"
REDIS_VALUE = "redis://:topsecret@cache.internal:6379"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_VALUE)
    monkeypatch.setenv("REDIS_URL", REDIS_VALUE)
    monkeypatch.setenv("API_TOKEN", "test-token")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _message(excinfo: pytest.ExceptionInfo[SystemExit]) -> str:
    message = str(excinfo.value)
    assert "\n" not in message
    assert "hunter2" not in message
    assert "topsecret" not in message
    return message


def test_missing_database_url_names_only_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL")

    with pytest.raises(SystemExit) as excinfo:
        validate_settings_at_startup()

    message = _message(excinfo)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" not in message


def test_missing_redis_url_names_only_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL")

    with pytest.raises(SystemExit) as excinfo:
        validate_settings_at_startup()

    message = _message(excinfo)
    assert "REDIS_URL" in message
    assert "DATABASE_URL" not in message


def test_both_missing_named_on_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.delenv("REDIS_URL")

    with pytest.raises(SystemExit) as excinfo:
        validate_settings_at_startup()

    message = _message(excinfo)
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message


@pytest.mark.parametrize("blank", ["", "   "])
@pytest.mark.parametrize("name", ["DATABASE_URL", "REDIS_URL"])
def test_blank_url_is_reported_as_missing(
    monkeypatch: pytest.MonkeyPatch, name: str, blank: str
) -> None:
    monkeypatch.setenv(name, blank)

    with pytest.raises(SystemExit) as excinfo:
        validate_settings_at_startup()

    assert name in _message(excinfo)


def test_create_app_exits_when_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL")

    with pytest.raises(SystemExit) as excinfo:
        create_app()

    message = _message(excinfo)
    assert "REDIS_URL" in message


def test_missing_api_token_keeps_lazy_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("API_TOKEN")

    validate_settings_at_startup()
    application = create_app()

    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/tenants/1")

    assert response.status_code == 401
