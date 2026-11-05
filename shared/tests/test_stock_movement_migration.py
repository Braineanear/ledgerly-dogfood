from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

INSERT_MOVEMENT = (
    "INSERT INTO stock_movement (tenant_id, product_id, warehouse, delta) "
    "VALUES (:tenant_id, :product_id, :warehouse, :delta)"
)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'movement.db'}"
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
        command.upgrade(config, "0005")
        connection.commit()
        yield config, connection
    engine.dispose()


def _movement(tenant_id: int, product_id: int, delta: int = 1) -> dict:
    return {
        "tenant_id": tenant_id,
        "product_id": product_id,
        "warehouse": "main",
        "delta": delta,
    }


def test_upgrade_creates_stock_movement_table(migrated) -> None:
    _config, connection = migrated
    inspector = sa.inspect(connection)
    columns = {c["name"] for c in inspector.get_columns("stock_movement")}
    assert columns == {
        "id",
        "tenant_id",
        "product_id",
        "warehouse",
        "delta",
        "created_at",
    }
    indexes = {
        i["name"]: i["column_names"] for i in inspector.get_indexes("stock_movement")
    }
    assert indexes == {
        "ix_stock_movement_tenant_product_warehouse": [
            "tenant_id",
            "product_id",
            "warehouse",
        ]
    }


def test_movement_created_at_defaults_and_delta_is_signed(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_MOVEMENT), _movement(1, 1, delta=-4))
    row = connection.execute(
        sa.text("SELECT delta, created_at FROM stock_movement")
    ).one()
    assert row[0] == -4
    assert row[1] is not None


def test_composite_foreign_key_rejects_tenant_mismatch(migrated) -> None:
    _config, connection = migrated
    # Product 1 belongs to tenant 1, so tenant 2 must be refused.
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MOVEMENT), _movement(2, 1))


def test_movement_requires_existing_product(migrated) -> None:
    _config, connection = migrated
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MOVEMENT), _movement(1, 99))


def test_downgrade_drops_stock_movement_and_keeps_other_tables(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0004")
    connection.commit()
    tables = set(sa.inspect(connection).get_table_names())
    assert "stock_movement" not in tables
    assert {"tenant", "product", "stock_level", "order"} <= tables
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
    tenants = connection.execute(sa.text("SELECT COUNT(*) FROM tenant")).scalar()
    assert tenants == 2
