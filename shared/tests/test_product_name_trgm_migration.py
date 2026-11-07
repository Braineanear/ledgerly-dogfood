import contextlib
import importlib.util
import io
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

from alembic import command

SHARED = Path(__file__).resolve().parents[1]
ALEMBIC_INI = SHARED / "alembic.ini"
MIGRATION = SHARED / "alembic" / "versions" / "0009_product_name_trgm.py"
INDEX = "ix_product_name_trgm"
PG_URL = os.environ.get("LEDGERLY_TEST_PG_URL")


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0009", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render(function) -> str:
    buffer = io.StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": buffer},
    )
    with Operations.context(context):
        function()
    return buffer.getvalue()


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'trgm.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(url)
    with engine.connect() as connection:
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
        command.upgrade(config, "0008")
        connection.commit()
        yield config, connection
    engine.dispose()


def _product_state(connection) -> tuple[set[str], set[str]]:
    inspector = sa.inspect(connection)
    columns = {c["name"] for c in inspector.get_columns("product")}
    indexes = {i["name"] for i in inspector.get_indexes("product")}
    return columns, indexes


def test_sqlite_upgrade_and_downgrade_are_no_ops(migrated) -> None:
    config, connection = migrated
    before = _product_state(connection)
    assert _load_migration().down_revision == "0008"

    command.upgrade(config, "0009")
    connection.commit()
    assert _product_state(connection) == before
    assert INDEX not in before[1]
    version = connection.execute(sa.text("SELECT version_num FROM alembic_version"))
    assert version.scalar() == "0009"
    products = connection.execute(sa.text("SELECT name FROM product")).all()
    assert [row[0] for row in products] == ["Widget"]

    command.downgrade(config, "0008")
    connection.commit()
    assert _product_state(connection) == before
    version = connection.execute(sa.text("SELECT version_num FROM alembic_version"))
    assert version.scalar() == "0008"
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1


def test_postgresql_upgrade_renders_extension_and_gin_index() -> None:
    module = _load_migration()
    assert module.revision == "0009"
    assert module.down_revision == "0008"

    sql = _render(module.upgrade)
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql
    assert INDEX in sql
    assert "USING gin" in sql
    assert "gin_trgm_ops" in sql
    assert "CREATE INDEX CONCURRENTLY" in sql
    assert f"{INDEX} ON product USING gin (name gin_trgm_ops)" in sql
    assert sql.index("CREATE EXTENSION") < sql.index("CREATE INDEX")


@pytest.mark.parametrize("invalid", [True, False])
def test_upgrade_removes_invalid_residual_index_before_retry(
    monkeypatch, invalid
) -> None:
    module = _load_migration()
    executed: list[str] = []

    class FakeResult:
        def first(self):
            return (1,) if invalid else None

    class FakeBind:
        def execute(self, statement, params=None):
            assert params == {"name": INDEX}
            return FakeResult()

    class FakeContext:
        as_sql = False

        class dialect:
            name = "postgresql"

        def autocommit_block(self):
            executed.append("autocommit")
            return contextlib.nullcontext()

    class FakeOp:
        f = staticmethod(lambda name: name)

        def get_context(self):
            return FakeContext()

        def get_bind(self):
            return FakeBind()

        def execute(self, statement):
            executed.append(str(statement))

        def create_index(self, name, *args, **kwargs):
            executed.append(f"create {name}")

    monkeypatch.setattr(module, "op", FakeOp())
    module.upgrade()

    drop = f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX}"
    assert (drop in executed) is invalid
    if invalid:
        assert executed.index(drop) < executed.index(f"create {INDEX}")
    assert executed[-1] == f"create {INDEX}"


def test_postgresql_downgrade_drops_index_but_not_extension() -> None:
    sql = _render(_load_migration().downgrade)
    assert "DROP INDEX CONCURRENTLY" in sql
    assert INDEX in sql
    assert "DROP EXTENSION" not in sql


@pytest.mark.skipif(not PG_URL, reason="set LEDGERLY_TEST_PG_URL to run on Postgres")
def test_live_postgres_creates_and_drops_trigram_index(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    config = Config(str(ALEMBIC_INI))
    engine = sa.create_engine(PG_URL)
    index_query = sa.text(
        "SELECT am.amname, oc.opcname FROM pg_index i "
        "JOIN pg_class c ON c.oid = i.indexrelid "
        "JOIN pg_am am ON am.oid = c.relam "
        "JOIN pg_opclass oc ON oc.oid = i.indclass[0] "
        "WHERE c.relname = :name"
    )
    extension_query = sa.text(
        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_trgm'"
    )
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        # Only touch a database whose state we can put back exactly:
        # either completely empty (the test creates, then removes, its
        # own tables) or already at 0009 (only the index is dropped and
        # recreated, so application data stays in place). A database
        # with tables but no alembic revision may hold unrelated data,
        # so it is never migrated or downgraded to base.
        initial = MigrationContext.configure(connection).get_current_revision()
        tables = sa.inspect(connection).get_table_names()
        connection.rollback()
        if not (initial == "0009" or (initial is None and not tables)):
            engine.dispose()
            pytest.skip(
                "LEDGERLY_TEST_PG_URL must be an empty database or one "
                f"at revision 0009 (found revision {initial}, "
                f"{len(tables)} tables)"
            )
        try:
            if initial == "0009":
                command.downgrade(config, "0008")
            else:
                command.upgrade(config, "0008")
            connection.commit()
            command.upgrade(config, "0009")
            connection.commit()
            assert connection.execute(extension_query).scalar() == 1
            rows = connection.execute(index_query, {"name": INDEX}).all()
            assert [tuple(row) for row in rows] == [("gin", "gin_trgm_ops")]

            command.downgrade(config, "0008")
            connection.commit()
            assert connection.execute(index_query, {"name": INDEX}).all() == []
            assert connection.execute(extension_query).scalar() == 1
        finally:
            # Restore the state found at the start, never more.
            connection.rollback()
            if initial == "0009":
                command.upgrade(config, "0009")
            else:
                # The database was empty, so everything in it now was
                # created by this test.
                command.downgrade(config, "base")
                connection.commit()
                connection.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))
            connection.commit()
    engine.dispose()
