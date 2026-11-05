"""Stock movements and the recomputation of stock levels from them.

Invariant: after recompute_stock_levels, each StockLevel.quantity equals
the sum of the StockMovement deltas for its (tenant_id, product_id,
warehouse). The result depends only on the movements, so running it
again changes nothing.

Concurrency: writers and recomputes serialize on the tenant row (shared
for appends, exclusive for a recompute) and then on the product row.
Both always lock in that order.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledgerly_shared.orm import Product, StockLevel, StockMovement, Tenant

Key = tuple[int, int, str]


class StockInvariantError(Exception):
    """Raised when movements sum to a negative quantity for some key."""


def _lock_tenants(
    session: Session, tenant_id: int | None, shared: bool = False
) -> list[int]:
    """Lock the tenant rows in scope and return their ids.

    A recompute takes an exclusive lock and an append takes a shared
    one, so appends run side by side but never alongside a recompute of
    the same tenant. Because the tenant row exists before any of its
    products, this also stops an append for a product created during a
    run, which no product lock could do. Rows are locked in id order.
    SQLAlchemy omits the lock clause on SQLite.
    """
    stmt = select(Tenant.id)
    if tenant_id is not None:
        stmt = stmt.where(Tenant.id == tenant_id)
    stmt = stmt.order_by(Tenant.id).with_for_update(read=shared)
    return [row[0] for row in session.execute(stmt)]


def _lock_products(
    session: Session,
    tenant_id: int | None,
    product_ids: list[int] | None = None,
) -> list[tuple[int, int]]:
    """Lock the product rows in scope and return their (tenant_id, id).

    Rows are locked in (tenant_id, id) order so that concurrent callers
    cannot deadlock. SQLAlchemy omits FOR UPDATE on SQLite.
    """
    stmt = select(Product.tenant_id, Product.id)
    if tenant_id is not None:
        stmt = stmt.where(Product.tenant_id == tenant_id)
    if product_ids is not None:
        stmt = stmt.where(Product.id.in_(product_ids))
    stmt = stmt.order_by(Product.tenant_id, Product.id).with_for_update()
    return [(row[0], row[1]) for row in session.execute(stmt)]


def append_stock_movement(
    session: Session,
    tenant_id: int,
    product_id: int,
    warehouse: str,
    delta: int,
) -> StockMovement:
    """Insert a movement after locking its tenant and product rows.

    This is the one sanctioned write path for movements. The tenant row
    is locked shared, then the product row exclusive, in that order.
    Recomputation locks the same rows, so appends and recomputes
    serialize. The caller owns the transaction.
    """
    _lock_tenants(session, tenant_id, shared=True)
    locked = _lock_products(session, tenant_id, [product_id])
    if not locked:
        raise ValueError(
            f"product {product_id} not found for tenant {tenant_id}"
        )
    movement = StockMovement(
        tenant_id=tenant_id,
        product_id=product_id,
        warehouse=warehouse,
        delta=delta,
    )
    session.add(movement)
    session.flush()
    return movement


def recompute_stock_levels(
    session: Session, tenant_id: int | None = None
) -> int:
    """Rebuild StockLevel rows from StockMovement rows.

    Limited to one tenant when tenant_id is given, otherwise every
    tenant. Returns the number of StockLevel rows inserted or changed,
    so an idempotent second run returns 0.

    Rules:
    - A negative total raises StockInvariantError before any write.
    - A StockLevel row with no movements is set to 0, not deleted.
    - The function never commits; the caller owns the transaction.

    All movement writes must go through append_stock_movement, or take
    a shared lock on the tenant row and then lock the product row, so
    they cannot interleave with a run. The tenant rows and then the
    product rows are locked before the movements are aggregated, in a
    separate statement, so a READ COMMITTED aggregate sees every
    committed movement of the locked tenants.

    Limit: a tenant created after the lock phase of a whole-scope run
    cannot be locked, so its movements may miss the run. A product
    created in a locked tenant is covered, because its append waits on
    the tenant lock. Anything that misses a run is picked up by the
    next one.
    """
    _lock_tenants(session, tenant_id)
    _lock_products(session, tenant_id)

    total = func.sum(StockMovement.delta)
    stmt = select(
        StockMovement.tenant_id,
        StockMovement.product_id,
        StockMovement.warehouse,
        total,
    ).group_by(
        StockMovement.tenant_id,
        StockMovement.product_id,
        StockMovement.warehouse,
    )
    if tenant_id is not None:
        stmt = stmt.where(StockMovement.tenant_id == tenant_id)
    totals: dict[Key, int] = {
        (row[0], row[1], row[2]): int(row[3]) for row in session.execute(stmt)
    }

    negative = sorted(key for key, value in totals.items() if value < 0)
    if negative:
        raise StockInvariantError(
            "negative stock total for (tenant_id, product_id, warehouse): "
            + ", ".join(str(key) for key in negative)
        )

    level_stmt = select(StockLevel)
    if tenant_id is not None:
        level_stmt = level_stmt.where(StockLevel.tenant_id == tenant_id)
    levels: dict[Key, StockLevel] = {
        (level.tenant_id, level.product_id, level.warehouse): level
        for level in session.scalars(level_stmt)
    }

    written = 0
    for key, quantity in totals.items():
        level = levels.get(key)
        if level is None:
            session.add(
                StockLevel(
                    tenant_id=key[0],
                    product_id=key[1],
                    warehouse=key[2],
                    quantity=quantity,
                )
            )
            written += 1
        elif level.quantity != quantity:
            level.quantity = quantity
            written += 1

    for key, level in levels.items():
        if key not in totals and level.quantity != 0:
            level.quantity = 0
            written += 1

    session.flush()
    return written
