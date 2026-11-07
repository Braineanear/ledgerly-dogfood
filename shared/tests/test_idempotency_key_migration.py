from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

INSERT_KEY = (
    "INSERT INTO idempotency_key "
    "(tenant_id, key, request_hash, response_status, response_body) "
    "VALUES (:tenant_id, :key, :request_hash, 201, '{}')"
)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'idempotency.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(url)

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
        connection.execute(sa.text("INSERT INTO tenant (id, name) VALUES (1, 'A')"))
        connection.execute(sa.text("INSERT INTO tenant (id, name) VALUES (2, 'B')"))
        connection.execute(
            sa.text(
                "INSERT INTO product (id, tenant_id, sku, name) "
                "VALUES (1, 1, 'SKU-1', 'Widget')"
            )
        )
        connection.commit()
        command.upgrade(config, "0007")
        connection.commit()
        yield config, connection
    engine.dispose()


def _key(tenant_id: int, key: str = "abc") -> dict:
    return {"tenant_id": tenant_id, "key": key, "request_hash": "h" * 64}


def test_upgrade_creates_idempotency_key_table(migrated) -> None:
    _config, connection = migrated
    inspector = sa.inspect(connection)
    assert "idempotency_key" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("idempotency_key")}
    assert columns == {
        "id",
        "tenant_id",
        "key",
        "request_hash",
        "response_status",
        "response_body",
        "created_at",
    }


def test_key_is_unique_per_tenant(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_KEY), _key(1))
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_KEY), _key(1))
    connection.rollback()
    connection.execute(sa.text(INSERT_KEY), _key(1))
    connection.execute(sa.text(INSERT_KEY), _key(2))
    count = connection.execute(
        sa.text("SELECT COUNT(*) FROM idempotency_key")
    ).scalar()
    assert count == 2


def test_key_requires_existing_tenant(migrated) -> None:
    _config, connection = migrated
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_KEY), _key(99))


def test_downgrade_drops_idempotency_key_and_keeps_other_tables(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0006")
    connection.commit()
    tables = set(sa.inspect(connection).get_table_names())
    assert "idempotency_key" not in tables
    assert {"tenant", "product", "stock_movement"} <= tables
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
    tenants = connection.execute(sa.text("SELECT COUNT(*) FROM tenant")).scalar()
    assert tenants == 2
