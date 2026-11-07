"""Add notes to product.

The column is optional free text, so it is nullable.

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-07 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain ALTER TABLE, not batch mode: a batch rebuild drops and
    # recreates product, which stock_level references, and fails when
    # SQLite enforces foreign keys.
    op.add_column("product", sa.Column("notes", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "notes")
