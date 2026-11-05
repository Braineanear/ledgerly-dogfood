from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

INSERT_ORDER = (
    'INSERT INTO "order" (product_id, quantity) VALUES (:product_id, :quantity)'
)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'order.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(url)

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(sa.text("INSERT INTO tenant (id, name) VALUES (1, 'A')"))
        connection.execute(
            sa.text(
                "INSERT INTO product (id, tenant_id, sku, name) "
                "VALUES (1, 1, 'SKU-1', 'Widget')"
            )
        )
        connection.commit()
        command.upgrade(config, "0003")
        connection.commit()
        yield config, connection
    engine.dispose()


def test_upgrade_creates_order_table_without_tenant_id(migrated) -> None:
    _config, connection = migrated
    columns = {c["name"] for c in sa.inspect(connection).get_columns("order")}
    assert columns == {"id", "product_id", "quantity", "created_at"}
    assert "tenant_id" not in columns


def test_order_created_at_defaults(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_ORDER), {"product_id": 1, "quantity": 3})
    row = connection.execute(sa.text('SELECT quantity, created_at FROM "order"')).one()
    assert row[0] == 3
    assert row[1] is not None


def test_order_requires_existing_product(migrated) -> None:
    _config, connection = migrated
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_ORDER), {"product_id": 99, "quantity": 1})


def test_order_quantity_must_not_be_negative(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_ORDER), {"product_id": 1, "quantity": 0})
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_ORDER), {"product_id": 1, "quantity": -1})


def test_downgrade_drops_order_and_keeps_other_tables(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0002")
    connection.commit()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    assert "order" not in tables
    assert {"product", "stock_level"} <= tables
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
