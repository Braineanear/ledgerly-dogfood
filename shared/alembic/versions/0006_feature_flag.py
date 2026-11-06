"""Create the feature_flag table.

A feature flag is a named switch that is off unless a row enables it.

Revision ID: 0006
Revises: 0005
Create Date: 2025-01-06 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flag",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_feature_flag")),
    )


def downgrade() -> None:
    op.drop_table("feature_flag")
