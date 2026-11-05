from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_price_migration_keeps_legacy_rows_with_null_values(
    tmp_path, monkeypatch
) -> None:
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(url)

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    command.upgrade(config, "0001")
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO tenant (id, name) VALUES (1, 'Acme')"))
        connection.execute(
            sa.text(
                "INSERT INTO product (id, tenant_id, sku, name) "
                "VALUES (1, 1, 'SKU-1', 'Widget')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO stock_level "
                "(id, tenant_id, product_id, warehouse, quantity) "
                "VALUES (1, 1, 1, 'main', 5)"
            )
        )

    # Run the migrations on a connection that enforces foreign keys.
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.commit()

        row = connection.execute(
            sa.text("SELECT sku, name, price_minor, currency FROM product")
        ).one()
        assert tuple(row) == ("SKU-1", "Widget", None, None)

        command.downgrade(config, "0001")
        connection.commit()

        inspector = sa.inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("product")}
        products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
        stock = connection.execute(sa.text("SELECT COUNT(*) FROM stock_level")).scalar()
    assert columns == {"id", "tenant_id", "sku", "name"}
    assert products == 1
    assert stock == 1
    engine.dispose()
