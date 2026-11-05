import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.sql import ClauseElement

from ledgerly_shared import (
    Base,
    Product,
    StockInvariantError,
    StockLevel,
    StockMovement,
    Tenant,
    append_stock_movement,
    recompute_stock_levels,
)


@pytest.fixture
def session(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'stock.db'}")

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert session.execute(sa.text("PRAGMA foreign_keys")).scalar() == 1
        yield session
    engine.dispose()


def add_tenant(session: Session, name: str = "A") -> int:
    tenant = Tenant(name=name)
    session.add(tenant)
    session.flush()
    return tenant.id


def add_product(session: Session, tenant_id: int, sku: str = "SKU-1") -> int:
    product = Product(tenant_id=tenant_id, sku=sku, name="Widget")
    session.add(product)
    session.flush()
    return product.id


def add_level(
    session: Session, tenant_id: int, product_id: int, warehouse: str, quantity: int
) -> None:
    session.add(
        StockLevel(
            tenant_id=tenant_id,
            product_id=product_id,
            warehouse=warehouse,
            quantity=quantity,
        )
    )
    session.flush()


def snapshot(session: Session) -> list[tuple]:
    """Every StockLevel column, ids included, in a stable order."""
    rows = session.execute(
        sa.select(
            StockLevel.id,
            StockLevel.tenant_id,
            StockLevel.product_id,
            StockLevel.warehouse,
            StockLevel.quantity,
        ).order_by(StockLevel.id)
    )
    return [tuple(row) for row in rows]


def quantities(session: Session) -> dict[tuple[int, int, str], int]:
    return {
        (tenant_id, product_id, warehouse): quantity
        for _id, tenant_id, product_id, warehouse, quantity in snapshot(session)
    }


def test_sums_movements_across_warehouses(session) -> None:
    tenant = add_tenant(session)
    first = add_product(session, tenant, "SKU-1")
    second = add_product(session, tenant, "SKU-2")
    append_stock_movement(session, tenant, first, "east", 5)
    append_stock_movement(session, tenant, first, "east", 3)
    append_stock_movement(session, tenant, first, "east", -2)
    append_stock_movement(session, tenant, first, "west", 4)
    append_stock_movement(session, tenant, second, "east", 1)

    written = recompute_stock_levels(session)

    assert written == 3
    assert quantities(session) == {
        (tenant, first, "east"): 6,
        (tenant, first, "west"): 4,
        (tenant, second, "east"): 1,
    }


def test_second_run_changes_nothing(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    append_stock_movement(session, tenant, product, "east", 5)
    append_stock_movement(session, tenant, product, "west", 2)
    add_level(session, tenant, product, "north", 9)

    assert recompute_stock_levels(session) == 3
    first = snapshot(session)
    assert len(first) == 3

    assert recompute_stock_levels(session) == 0
    assert snapshot(session) == first
    session.commit()
    assert recompute_stock_levels(session) == 0
    assert snapshot(session) == first


def test_fixes_drift_in_place(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    append_stock_movement(session, tenant, product, "east", 5)
    append_stock_movement(session, tenant, product, "west", 2)
    add_level(session, tenant, product, "east", 99)
    before = snapshot(session)
    east_id = before[0][0]

    written = recompute_stock_levels(session)

    assert written == 2
    assert quantities(session) == {
        (tenant, product, "east"): 5,
        (tenant, product, "west"): 2,
    }
    # The drifted row was updated, not replaced.
    assert snapshot(session)[0][0] == east_id


def test_row_without_movements_is_set_to_zero_not_deleted(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    add_level(session, tenant, product, "east", 7)

    assert recompute_stock_levels(session) == 1

    assert quantities(session) == {(tenant, product, "east"): 0}


def test_movements_summing_to_zero_give_a_zero_level(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    append_stock_movement(session, tenant, product, "east", 4)
    append_stock_movement(session, tenant, product, "east", -4)
    add_level(session, tenant, product, "east", 4)

    assert recompute_stock_levels(session) == 1

    assert quantities(session) == {(tenant, product, "east"): 0}


def test_negative_total_raises_and_writes_nothing(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    append_stock_movement(session, tenant, product, "east", 5)
    append_stock_movement(session, tenant, product, "west", -3)
    add_level(session, tenant, product, "east", 99)
    add_level(session, tenant, product, "north", 8)
    session.commit()
    before = snapshot(session)

    with pytest.raises(StockInvariantError) as raised:
        recompute_stock_levels(session)

    assert str((tenant, product, "west")) in str(raised.value)
    assert not session.new
    assert not session.dirty
    assert snapshot(session) == before
    session.rollback()
    assert snapshot(session) == before


def test_tenant_scoped_run_leaves_other_tenants_alone(session) -> None:
    first = add_tenant(session, "A")
    second = add_tenant(session, "B")
    first_product = add_product(session, first)
    second_product = add_product(session, second)
    append_stock_movement(session, first, first_product, "east", 5)
    append_stock_movement(session, second, second_product, "east", 6)
    add_level(session, first, first_product, "east", 99)
    add_level(session, second, second_product, "east", 99)
    add_level(session, second, second_product, "west", 3)

    assert recompute_stock_levels(session, tenant_id=first) == 1

    assert quantities(session) == {
        (first, first_product, "east"): 5,
        (second, second_product, "east"): 99,
        (second, second_product, "west"): 3,
    }

    assert recompute_stock_levels(session, tenant_id=second) == 2
    assert quantities(session) == {
        (first, first_product, "east"): 5,
        (second, second_product, "east"): 6,
        (second, second_product, "west"): 0,
    }


def test_tenant_scoped_run_ignores_another_tenants_negative_total(session) -> None:
    first = add_tenant(session, "A")
    second = add_tenant(session, "B")
    first_product = add_product(session, first)
    second_product = add_product(session, second)
    append_stock_movement(session, first, first_product, "east", 5)
    append_stock_movement(session, second, second_product, "east", -1)

    assert recompute_stock_levels(session, tenant_id=first) == 1
    assert quantities(session) == {(first, first_product, "east"): 5}

    with pytest.raises(StockInvariantError):
        recompute_stock_levels(session)


def test_whole_scope_run_covers_every_tenant(session) -> None:
    first = add_tenant(session, "A")
    second = add_tenant(session, "B")
    first_product = add_product(session, first)
    second_product = add_product(session, second)
    append_stock_movement(session, first, first_product, "east", 1)
    append_stock_movement(session, second, second_product, "east", 2)

    assert recompute_stock_levels(session) == 2

    assert quantities(session) == {
        (first, first_product, "east"): 1,
        (second, second_product, "east"): 2,
    }


def test_empty_tables_write_nothing(session) -> None:
    assert recompute_stock_levels(session) == 0
    assert snapshot(session) == []
    tenant = add_tenant(session)
    add_product(session, tenant)
    assert recompute_stock_levels(session, tenant_id=tenant) == 0
    assert snapshot(session) == []


def test_unknown_tenant_scope_writes_nothing(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    append_stock_movement(session, tenant, product, "east", 2)

    assert recompute_stock_levels(session, tenant_id=tenant + 100) == 0
    assert snapshot(session) == []


def test_append_then_recompute(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)

    movement = append_stock_movement(session, tenant, product, "east", 5)

    assert isinstance(movement, StockMovement)
    assert movement.id is not None
    assert (movement.tenant_id, movement.product_id) == (tenant, product)
    assert (movement.warehouse, movement.delta) == ("east", 5)
    assert recompute_stock_levels(session) == 1
    append_stock_movement(session, tenant, product, "east", 2)
    assert recompute_stock_levels(session) == 1
    assert quantities(session) == {(tenant, product, "east"): 7}


def test_append_rejects_unknown_product_and_wrong_tenant(session) -> None:
    first = add_tenant(session, "A")
    second = add_tenant(session, "B")
    product = add_product(session, first)

    with pytest.raises(ValueError):
        append_stock_movement(session, first, product + 100, "east", 1)
    with pytest.raises(ValueError):
        append_stock_movement(session, second, product, "east", 1)
    assert session.scalar(sa.select(sa.func.count(StockMovement.id))) == 0


# Lock shape. SQLite ignores FOR UPDATE, so these tests compile each
# statement the session sends against the PostgreSQL dialect instead.


@contextmanager
def recorded_sql(session: Session):
    statements: list[str] = []

    def record(_conn, clauseelement, _multiparams, _params, _options) -> None:
        if isinstance(clauseelement, ClauseElement):
            compiled = clauseelement.compile(dialect=postgresql.dialect())
            statements.append(" ".join(str(compiled).split()))

    engine = session.get_bind()
    sa.event.listen(engine, "before_execute", record)
    try:
        yield statements
    finally:
        sa.event.remove(engine, "before_execute", record)


def index_of(statements: list[str], *fragments: str) -> int:
    for position, sql in enumerate(statements):
        if all(fragment in sql for fragment in fragments):
            return position
    raise AssertionError(f"no statement containing {fragments} in {statements}")


def test_recompute_locks_tenants_then_products_before_aggregating(session) -> None:
    tenant = add_tenant(session)
    add_product(session, tenant)
    session.commit()

    with recorded_sql(session) as statements:
        recompute_stock_levels(session, tenant_id=tenant)

    tenant_lock = index_of(statements, "FROM tenant", "FOR UPDATE")
    product_lock = index_of(statements, "FROM product", "FOR UPDATE")
    aggregate = index_of(statements, "sum(stock_movement.delta)")
    assert tenant_lock < product_lock < aggregate
    assert "FOR SHARE" not in statements[tenant_lock]
    # Every query is scoped to the tenant.
    assert "tenant.id = " in statements[tenant_lock]
    assert "product.tenant_id = " in statements[product_lock]
    assert "stock_movement.tenant_id = " in statements[aggregate]


def test_whole_scope_recompute_locks_without_a_tenant_filter(session) -> None:
    with recorded_sql(session) as statements:
        recompute_stock_levels(session)

    tenant_lock = index_of(statements, "FROM tenant", "FOR UPDATE")
    product_lock = index_of(statements, "FROM product", "FOR UPDATE")
    assert "WHERE" not in statements[tenant_lock]
    assert "WHERE" not in statements[product_lock]


def test_append_locks_tenant_shared_then_product_before_inserting(session) -> None:
    tenant = add_tenant(session)
    product = add_product(session, tenant)
    session.commit()

    with recorded_sql(session) as statements:
        append_stock_movement(session, tenant, product, "east", 1)

    tenant_lock = index_of(statements, "FROM tenant", "FOR SHARE")
    product_lock = index_of(statements, "FROM product", "FOR UPDATE")
    insert = index_of(statements, "INSERT INTO stock_movement")
    assert tenant_lock < product_lock < insert
    assert "product.id IN" in statements[product_lock]


# SQLite cannot block on a row lock, so everything above leaves the real
# blocking behaviour untested. This test closes that gap where a
# PostgreSQL server is available.

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")


@pytest.fixture
def postgres_engine():
    schema = f"ledgerly_test_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(POSTGRES_URL)
    with admin.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(
        POSTGRES_URL, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.mark.skipif(
    not POSTGRES_URL,
    reason=(
        "TEST_POSTGRES_URL is not set: row-lock blocking between "
        "recompute_stock_levels and append_stock_movement is only "
        "exercised on PostgreSQL, and the SQLite tests do not prove it"
    ),
)
def test_append_blocks_until_recompute_commits(postgres_engine) -> None:
    with Session(postgres_engine) as setup:
        tenant = add_tenant(setup)
        product = add_product(setup, tenant)
        append_stock_movement(setup, tenant, product, "east", 5)
        setup.commit()

    entered = threading.Event()
    appended = threading.Event()

    def append_in_thread() -> None:
        try:
            with Session(postgres_engine) as other:
                other.execute(sa.text("SET LOCAL lock_timeout = '20s'"))
                entered.set()
                append_stock_movement(other, tenant, product, "east", 7)
                appended.set()
                other.commit()
        finally:
            entered.set()

    holder = Session(postgres_engine)
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            assert recompute_stock_levels(holder, tenant_id=tenant) == 1
            future = pool.submit(append_in_thread)
            assert entered.wait(10)
            assert not appended.wait(1.0), "append did not wait for the recompute"
            holder.commit()
            assert appended.wait(20), "append stayed blocked after the commit"
        finally:
            holder.close()
        # Re-raises anything the append thread failed with.
        future.result(timeout=20)

    with Session(postgres_engine) as check:
        # The first run could not see the blocked append; the next one does.
        assert recompute_stock_levels(check, tenant_id=tenant) == 1
        check.commit()
        assert quantities(check) == {(tenant, product, "east"): 12}
        total = check.scalar(sa.select(sa.func.sum(StockMovement.delta)))
        assert total == 12
