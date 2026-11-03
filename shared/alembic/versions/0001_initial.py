"""Create the tenant, product and stock_level tables.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tenant"),
    )
    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenant.id"], name="fk_product_tenant_id_tenant"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_id_sku"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_product_tenant_id_id"),
    )
    op.create_table(
        "stock_level",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quantity >= 0", name="ck_stock_level_quantity_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name="fk_stock_level_tenant_id_product_id_product",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_level"),
        sa.UniqueConstraint(
            "product_id", "warehouse", name="uq_stock_level_product_id_warehouse"
        ),
    )


def downgrade() -> None:
    op.drop_table("stock_level")
    op.drop_table("product")
    op.drop_table("tenant")
