"""Create the idempotency_key table.

A row stores the response to one request made with an Idempotency-Key
header, so a replay can return it. Keys are unique per tenant.

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
    op.create_table(
        "idempotency_key",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name=op.f("fk_idempotency_key_tenant_id_tenant"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_key")),
        sa.UniqueConstraint(
            "tenant_id", "key", name=op.f("uq_idempotency_key_tenant_id_key")
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_key")
