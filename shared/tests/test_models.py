import sqlalchemy as sa
from sqlalchemy.orm import Session

from ledgerly_shared import PlaceholderModel
from ledgerly_shared.models import PlaceholderModel as ModelFromModule
from ledgerly_shared.orm import Base, Product, Tenant


def test_product_notes_is_nullable_and_round_trips() -> None:
    assert Product.__table__.c.notes.nullable is True

    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tenant(id=1, name="Acme"))
        session.add(Product(id=1, tenant_id=1, sku="SKU-1", name="Plain"))
        session.add(
            Product(id=2, tenant_id=1, sku="SKU-2", name="Noted", notes="hello")
        )
        session.commit()

        assert session.get(Product, (1)).notes is None
        assert session.get(Product, (2)).notes == "hello"
    engine.dispose()


def test_placeholder_model_is_importable() -> None:
    model = PlaceholderModel(identifier="placeholder")

    assert ModelFromModule is PlaceholderModel
    assert model.identifier == "placeholder"
