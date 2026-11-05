"""Create the order table.

An order has no tenant_id: its tenant is reachable only through
product.tenant_id, so the foreign key to product is plain.

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-03 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.f marks each name as final so the naming convention does not
    # prefix it a second time.
    op.create_table(
        "order",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity >= 0", name=op.f("ck_order_quantity_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_order_product_id_product"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order")),
    )


def downgrade() -> None:
    op.drop_table("order")
