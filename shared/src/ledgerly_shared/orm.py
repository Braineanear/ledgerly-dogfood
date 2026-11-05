"""SQLAlchemy models for tenants, products, stock levels and orders."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base whose metadata gives every constraint a stable name."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Tenant(Base):
    """A customer account; the unscoped root that owns all other rows."""

    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    # The client-side default covers SQLite, where migration 0004 cannot
    # add a database-level default to the existing table.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )


class Product(Base):
    """A product sold by one tenant, identified by a SKU unique per tenant."""

    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku"),
        # Target of the composite foreign key from stock_level.
        UniqueConstraint("tenant_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    # Nullable only for rows that predate migration 0002; the API
    # always requires both on create.
    price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)


class StockLevel(Base):
    """The quantity of one product held in one warehouse."""

    __tablename__ = "stock_level"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        UniqueConstraint("product_id", "warehouse"),
        # Keeps the row's tenant equal to its product's tenant.
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(Integer)
    warehouse: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)


class Order(Base):
    """A quantity of one product ordered at a point in time."""

    __tablename__ = "order"
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_non_negative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # The tenant is reachable only through product.tenant_id, so this
    # foreign key is plain: the composite (tenant_id, id) unique
    # constraint on product does not apply.
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
