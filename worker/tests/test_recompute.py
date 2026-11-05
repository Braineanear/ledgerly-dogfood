"""Tests for the stock recompute CLI, using a temporary SQLite file."""

import pytest
from ledgerly_shared.orm import (
    Base,
    Product,
    StockLevel,
    StockMovement,
    Tenant,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ledgerly_worker import recompute


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'stock.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        tenant = Tenant(name="Acme")
        session.add(tenant)
        session.flush()
        product = Product(
            tenant_id=tenant.id,
            sku="SKU-1",
            name="Widget",
            price_minor=100,
            currency="USD",
        )
        session.add(product)
        session.flush()
        for warehouse, delta in (("a", 5), ("a", 3), ("b", 2)):
            session.add(
                StockMovement(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    warehouse=warehouse,
                    delta=delta,
                )
            )
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    return url


def snapshot(url):
    engine = create_engine(url)
    with Session(engine) as session:
        rows = session.execute(
            select(
                StockLevel.id,
                StockLevel.tenant_id,
                StockLevel.product_id,
                StockLevel.warehouse,
                StockLevel.quantity,
            ).order_by(StockLevel.id)
        ).all()
    engine.dispose()
    return [tuple(row) for row in rows]


def test_successful_run_matches_invariant(db_url):
    assert recompute.main([]) == 0
    quantities = {row[3]: row[4] for row in snapshot(db_url)}
    assert quantities == {"a": 8, "b": 2}


def test_second_run_changes_nothing(db_url):
    assert recompute.main([]) == 0
    first = snapshot(db_url)
    assert recompute.main([]) == 0
    assert snapshot(db_url) == first


def test_tenant_id_option_scopes_the_run(db_url):
    assert recompute.main(["--tenant-id", "999"]) == 0
    assert snapshot(db_url) == []


def test_negative_total_exits_non_zero_and_writes_nothing(db_url, capsys):
    engine = create_engine(db_url)
    with Session(engine) as session, session.begin():
        product = session.scalars(select(Product)).one()
        session.add(
            StockMovement(
                tenant_id=product.tenant_id,
                product_id=product.id,
                warehouse="b",
                delta=-10,
            )
        )
    engine.dispose()
    assert recompute.main([]) == 1
    assert "negative stock total" in capsys.readouterr().err
    assert snapshot(db_url) == []


def test_missing_database_url_exits_non_zero(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert recompute.main([]) == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_engine_is_built_from_database_url(db_url, monkeypatch):
    calls = []

    def spy(url, *args, **kwargs):
        calls.append(url)
        return create_engine(url, *args, **kwargs)

    monkeypatch.setattr(recompute, "create_engine", spy)
    assert recompute.main([]) == 0
    assert calls == [db_url]
