"""Tests for the seed script, using in-memory SQLite databases."""

import pytest
from ledgerly_shared.orm import Base, Product, Tenant
from sqlalchemy import Engine, create_engine, func, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ledgerly_api import seed as seed_module
from ledgerly_api.seed import SchemaMissing, SeedRefused, seed


def _new_engine() -> Engine:
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def engine() -> Engine:
    created = _new_engine()
    Base.metadata.create_all(created)
    return created


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def test_seed_writes_two_tenants_and_twenty_products(engine: Engine) -> None:
    seed(engine)
    assert _count(engine, Tenant) == 2
    assert _count(engine, Product) == 20
    with Session(engine) as session:
        for tenant in session.scalars(select(Tenant)):
            skus = [
                product.sku
                for product in session.scalars(
                    select(Product).where(Product.tenant_id == tenant.id)
                )
            ]
            assert len(skus) == 10
            assert len(set(skus)) == 10


def test_second_seed_is_refused(engine: Engine) -> None:
    seed(engine)
    with pytest.raises(SeedRefused):
        seed(engine)
    assert _count(engine, Tenant) == 2
    assert _count(engine, Product) == 20


def test_existing_tenant_is_refused(engine: Engine) -> None:
    with Session(engine) as session, session.begin():
        session.add(Tenant(name="Existing"))
    with pytest.raises(SeedRefused):
        seed(engine)
    assert _count(engine, Tenant) == 1
    assert _count(engine, Product) == 0


def test_missing_schema_raises_and_creates_nothing() -> None:
    empty = _new_engine()
    with pytest.raises(SchemaMissing):
        seed(empty)
    assert inspect(empty).get_table_names() == []


def test_main_returns_zero_on_success(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    assert seed_module.main() == 0
    assert "seeded 2 tenants and 20 products" in capsys.readouterr().out


def test_main_returns_one_on_refusal(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(seed_module, "get_engine", lambda: engine)
    seed(engine)
    assert seed_module.main() == 1
    assert "seed refused" in capsys.readouterr().err
    assert _count(engine, Tenant) == 2


def test_main_returns_two_on_missing_schema(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = _new_engine()
    monkeypatch.setattr(seed_module, "get_engine", lambda: empty)
    assert seed_module.main() == 2
    assert "Alembic" in capsys.readouterr().err
