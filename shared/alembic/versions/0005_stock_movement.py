"""Create the stock_movement table.

A movement is a signed change to one product's stock in one warehouse.
Stock levels are recomputed as the sum of movements. Like stock_level,
the composite foreign key keeps tenant_id equal to the product's tenant.

Revision ID: 0005
Revises: 0004
Create Date: 2025-01-05 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_movement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=64), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["product.tenant_id", "product.id"],
            name=op.f("fk_stock_movement_tenant_id_product_id_product"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movement")),
    )
    op.create_index(
        op.f("ix_stock_movement_tenant_product_warehouse"),
        "stock_movement",
        ["tenant_id", "product_id", "warehouse"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stock_movement_tenant_product_warehouse"),
        table_name="stock_movement",
    )
    op.drop_table("stock_movement")
