"""Create the app_user and tenant_membership tables.

A user is identified by the hash of a secret token. A membership gives
one user the role admin or member in one tenant.

Revision ID: 0010
Revises: 0009
Create Date: 2025-01-09 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_app_user_token_hash")),
    )
    op.create_table(
        "tenant_membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'member')",
            name=op.f("ck_tenant_membership_role_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenant.id"],
            name=op.f("fk_tenant_membership_tenant_id_tenant"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_tenant_membership_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_membership")),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            name=op.f("uq_tenant_membership_tenant_id_user_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("tenant_membership")
    op.drop_table("app_user")
