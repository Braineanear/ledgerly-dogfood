from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from ledgerly_shared.orm import Tenant

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

INSERT_PRODUCT = (
    "INSERT INTO product (tenant_id, sku, name) VALUES (:tenant_id, :sku, 'W')"
)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'tenant.db'}"
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
        connection.execute(
            sa.text(
                "INSERT INTO product (id, tenant_id, sku, name) "
                "VALUES (1, 1, 'SKU-1', 'Widget')"
            )
        )
        connection.commit()
        command.upgrade(config, "0004")
        connection.commit()
        yield config, connection
    engine.dispose()


def _foreign_key_violations(connection) -> list:
    return connection.execute(sa.text("PRAGMA foreign_key_check")).fetchall()


def test_upgrade_backfills_existing_tenant_and_keeps_products(migrated) -> None:
    _config, connection = migrated
    row = connection.execute(sa.text("SELECT name, created_at FROM tenant")).one()
    assert row[0] == "A"
    assert row[1] is not None
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
    assert _foreign_key_violations(connection) == []


def test_foreign_key_still_enforced_after_upgrade(migrated) -> None:
    _config, connection = migrated
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_PRODUCT), {"tenant_id": 99, "sku": "SKU-2"})


def test_orm_insert_gets_created_at(migrated) -> None:
    _config, connection = migrated
    with Session(bind=connection) as session:
        tenant = Tenant(name="B")
        session.add(tenant)
        session.flush()
        session.refresh(tenant)
        assert tenant.created_at is not None


def test_downgrade_removes_column_and_keeps_rows(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0003")
    connection.commit()
    columns = {c["name"] for c in sa.inspect(connection).get_columns("tenant")}
    assert columns == {"id", "name"}
    assert connection.execute(sa.text("SELECT COUNT(*) FROM tenant")).scalar() == 1
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
    assert _foreign_key_violations(connection) == []
