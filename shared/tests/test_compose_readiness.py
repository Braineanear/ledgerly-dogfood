from pathlib import Path

import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "compose.yaml"


def _services():
    return yaml.safe_load(COMPOSE.read_text())["services"]


def test_api_waits_for_healthy_postgres():
    services = _services()
    condition = services["api"]["depends_on"]["postgres"]["condition"]
    assert condition == "service_healthy"


def test_postgres_has_pg_isready_healthcheck():
    check = _services()["postgres"]["healthcheck"]["test"]
    joined = check if isinstance(check, str) else " ".join(check)
    assert "pg_isready" in joined


def test_postgres_healthcheck_runs_in_the_container():
    healthcheck = _services()["postgres"]["healthcheck"]

    assert healthcheck.get("disable") is not True
    assert healthcheck["test"][0] == "CMD-SHELL"
    assert "$${POSTGRES_USER}" in healthcheck["test"][1]
    assert "$${POSTGRES_DB}" in healthcheck["test"][1]


def test_api_postgres_dependency_uses_long_form_condition():
    dependency = _services()["api"]["depends_on"]["postgres"]

    assert isinstance(dependency, dict)
    assert dependency == {"condition": "service_healthy"}
