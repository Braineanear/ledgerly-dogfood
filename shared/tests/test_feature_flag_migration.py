from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'flag.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(url)
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0006")
        connection.commit()
        yield config, connection
    engine.dispose()


def test_upgrade_creates_feature_flag_table(migrated) -> None:
    _config, connection = migrated
    columns = {c["name"] for c in sa.inspect(connection).get_columns("feature_flag")}
    assert columns == {"name", "enabled"}


def test_name_is_primary_key_and_enabled_not_null(migrated) -> None:
    _config, connection = migrated
    inspector = sa.inspect(connection)
    pk = inspector.get_pk_constraint("feature_flag")
    assert pk["constrained_columns"] == ["name"]
    columns = {c["name"]: c for c in inspector.get_columns("feature_flag")}
    assert columns["enabled"]["nullable"] is False
    assert columns["name"]["nullable"] is False


def test_enabled_defaults_to_false(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text("INSERT INTO feature_flag (name) VALUES ('beta')"))
    enabled = connection.execute(
        sa.text("SELECT enabled FROM feature_flag WHERE name = 'beta'")
    ).scalar()
    assert not enabled


def test_duplicate_name_is_rejected(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text("INSERT INTO feature_flag (name) VALUES ('beta')"))
    with pytest.raises(IntegrityError):
        connection.execute(sa.text("INSERT INTO feature_flag (name) VALUES ('beta')"))


def test_downgrade_drops_feature_flag_and_keeps_other_tables(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0005")
    connection.commit()
    tables = set(sa.inspect(connection).get_table_names())
    assert "feature_flag" not in tables
    assert {"tenant", "product", "stock_movement"} <= tables
