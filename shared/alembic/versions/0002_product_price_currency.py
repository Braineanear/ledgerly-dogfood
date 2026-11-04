"""Add price_minor and currency to product.

The columns are nullable only so that rows created before this
migration keep NULL instead of a fabricated price or currency. The API
always requires both when it creates a product.

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain ALTER TABLE statements, not batch mode: a batch rebuild
    # drops and recreates product, which stock_level references, and
    # fails when SQLite enforces foreign keys.
    op.add_column("product", sa.Column("price_minor", sa.BigInteger(), nullable=True))
    op.add_column("product", sa.Column("currency", sa.String(length=3), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "currency")
    op.drop_column("product", "price_minor")
