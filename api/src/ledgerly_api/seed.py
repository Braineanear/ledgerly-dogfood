"""Seed a migrated, empty database with two tenants and twenty products."""

import sys

from ledgerly_shared.orm import Product, Tenant
from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from ledgerly_api.db import get_engine

TENANT_NAMES = ("Acme Traders", "Birch Supplies")
PRODUCTS_PER_TENANT = 10


class SeedRefused(Exception):
    """The tenant table already has rows."""


class SchemaMissing(Exception):
    """The tenant or product table does not exist."""


def seed(engine: Engine) -> None:
    """Write 2 tenants and 20 products, or raise without writing."""
    inspector = inspect(engine)
    if not (inspector.has_table("tenant") and inspector.has_table("product")):
        raise SchemaMissing(
            "tenant and product tables are missing; run the Alembic "
            "migrations against the same DATABASE_URL first"
        )
    with Session(engine) as session, session.begin():
        if session.scalars(select(Tenant.id).limit(1)).first() is not None:
            raise SeedRefused("tenant table already has rows; not seeding")
        for tenant_name in TENANT_NAMES:
            tenant = Tenant(name=tenant_name)
            session.add(tenant)
            session.flush()
            for number in range(1, PRODUCTS_PER_TENANT + 1):
                session.add(
                    Product(
                        tenant_id=tenant.id,
                        sku=f"SKU-{number:03d}",
                        name=f"{tenant_name} product {number}",
                        price_minor=500 * number,
                        currency="USD",
                    )
                )


def main() -> int:
    """Seed the configured database and return the exit code."""
    try:
        seed(get_engine())
    except SeedRefused as exc:
        print(f"seed refused: {exc}", file=sys.stderr)
        return 1
    except SchemaMissing as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 2
    total = len(TENANT_NAMES) * PRODUCTS_PER_TENANT
    print(f"seeded {len(TENANT_NAMES)} tenants and {total} products")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
