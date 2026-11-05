"""Add tenant.created_at.

Existing tenants are backfilled with the migration time. The table is
never rebuilt (no batch_alter_table): product.tenant_id references it.

Revision ID: 0004
Revises: 0003
Create Date: 2025-01-04 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite rejects ADD COLUMN with a non-constant default, and
        # NOT NULL without a default. Add a nullable column and backfill;
        # the ORM default supplies the value for new rows.
        op.add_column(
            "tenant",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute("UPDATE tenant SET created_at = CURRENT_TIMESTAMP")
    else:
        op.add_column(
            "tenant",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )


def downgrade() -> None:
    op.drop_column("tenant", "created_at")
