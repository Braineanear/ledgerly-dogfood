from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

INSERT_USER = "INSERT INTO app_user (id, name, token_hash) VALUES (:id, 'U', :hash)"
INSERT_MEMBER = (
    "INSERT INTO tenant_membership (tenant_id, user_id, role) "
    "VALUES (:tenant_id, :user_id, :role)"
)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'membership.db'}"
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
        command.upgrade(config, "0010")
        connection.commit()
        yield config, connection
    engine.dispose()


def _member(tenant_id: int, user_id: int, role: str = "member") -> dict:
    return {"tenant_id": tenant_id, "user_id": user_id, "role": role}


def test_upgrade_creates_both_tables(migrated) -> None:
    _config, connection = migrated
    inspector = sa.inspect(connection)
    assert {"app_user", "tenant_membership"} <= set(inspector.get_table_names())
    users = {c["name"] for c in inspector.get_columns("app_user")}
    assert users == {"id", "name", "token_hash", "created_at"}
    members = {c["name"] for c in inspector.get_columns("tenant_membership")}
    assert members == {"id", "tenant_id", "user_id", "role"}


def test_token_hash_is_unique(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_USER), {"id": 2, "hash": "a" * 64})


def test_membership_is_unique_per_tenant_and_user(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    connection.execute(sa.text(INSERT_MEMBER), _member(1, 1))
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MEMBER), _member(1, 1, "admin"))
    connection.rollback()
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    connection.execute(sa.text(INSERT_MEMBER), _member(1, 1))
    connection.execute(sa.text(INSERT_MEMBER), _member(2, 1))


@pytest.mark.parametrize("role", ["owner", "", "ADMIN"])
def test_invalid_role_is_rejected(migrated, role) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MEMBER), _member(1, 1, role))


@pytest.mark.parametrize("role", ["admin", "member"])
def test_valid_roles_are_accepted(migrated, role) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    connection.execute(sa.text(INSERT_MEMBER), _member(1, 1, role))


def test_membership_requires_existing_tenant(migrated) -> None:
    _config, connection = migrated
    connection.execute(sa.text(INSERT_USER), {"id": 1, "hash": "a" * 64})
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MEMBER), _member(99, 1))


def test_membership_requires_existing_user(migrated) -> None:
    _config, connection = migrated
    with pytest.raises(IntegrityError):
        connection.execute(sa.text(INSERT_MEMBER), _member(1, 99))


def test_downgrade_drops_new_tables_and_keeps_others(migrated) -> None:
    config, connection = migrated
    connection.rollback()
    command.downgrade(config, "0009")
    connection.commit()
    tables = set(sa.inspect(connection).get_table_names())
    assert not {"app_user", "tenant_membership"} & tables
    assert {"tenant", "product", "idempotency_key"} <= tables
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    assert products == 1
    tenants = connection.execute(sa.text("SELECT COUNT(*) FROM tenant")).scalar()
    assert tenants == 2
    assert _version(connection) == "0009"


TRGM_INDEX = "ix_product_name_trgm"


def _version(connection) -> str:
    query = sa.text("SELECT version_num FROM alembic_version")
    return connection.execute(query).scalar()


def _counts(connection) -> tuple[int, int]:
    tenants = connection.execute(sa.text("SELECT COUNT(*) FROM tenant")).scalar()
    products = connection.execute(sa.text("SELECT COUNT(*) FROM product")).scalar()
    return tenants, products


def _index_names(connection) -> set[str]:
    return {i["name"] for i in sa.inspect(connection).get_indexes("product")}


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """A database at 0003 holding tenant and product rows, to migrate from."""
    url = f"sqlite:///{tmp_path / 'transitions.db'}"
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
        yield config, connection
    engine.dispose()


def _move(config, connection, action, revision) -> None:
    connection.rollback()
    action(config, revision)
    connection.commit()


@pytest.mark.parametrize("start", ["0008", "0009"])
def test_upgrade_to_0010_from_earlier_revisions(seeded, start) -> None:
    config, connection = seeded
    _move(config, connection, command.upgrade, start)
    assert _version(connection) == start
    assert "app_user" not in sa.inspect(connection).get_table_names()

    _move(config, connection, command.upgrade, "0010")

    assert _version(connection) == "0010"
    tables = set(sa.inspect(connection).get_table_names())
    assert {"app_user", "tenant_membership"} <= tables
    assert _counts(connection) == (2, 1)
    # 0009 only acts on Postgres, so SQLite never gains the trigram index.
    assert TRGM_INDEX not in _index_names(connection)


def test_downgrade_0010_to_0009_then_0008(seeded) -> None:
    config, connection = seeded
    _move(config, connection, command.upgrade, "0010")
    assert _version(connection) == "0010"

    _move(config, connection, command.downgrade, "0009")
    assert _version(connection) == "0009"
    assert not {"app_user", "tenant_membership"} & set(
        sa.inspect(connection).get_table_names()
    )
    assert _counts(connection) == (2, 1)
    assert TRGM_INDEX not in _index_names(connection)

    _move(config, connection, command.downgrade, "0008")
    assert _version(connection) == "0008"
    assert "idempotency_key" in sa.inspect(connection).get_table_names()
    assert _counts(connection) == (2, 1)
    assert TRGM_INDEX not in _index_names(connection)


def test_downgrade_0010_straight_to_0008(seeded) -> None:
    config, connection = seeded
    _move(config, connection, command.upgrade, "0010")

    _move(config, connection, command.downgrade, "0008")

    assert _version(connection) == "0008"
    tables = set(sa.inspect(connection).get_table_names())
    assert not {"app_user", "tenant_membership"} & tables
    assert _counts(connection) == (2, 1)
