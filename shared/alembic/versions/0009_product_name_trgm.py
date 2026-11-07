"""Add a trigram index on product.name for name search.

Postgres only: install the pg_trgm extension and create a GIN index with
gin_trgm_ops so ILIKE '%text%' searches can use it. On other dialects
(sqlite) this migration does nothing. The downgrade drops only the index
and leaves the extension installed, since other objects may rely on it.
The index is not declared on the ORM model, so Base.metadata.create_all
on sqlite is unaffected.

Creating the extension needs the CREATE privilege on the database.

Revision ID: 0009
Revises: 0008
Create Date: 2025-01-08 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_product_name_trgm"


def _is_postgresql() -> bool:
    # get_context() also works in offline (--sql) mode, where there is
    # no connection to ask.
    return op.get_context().dialect.name == "postgresql"


def _has_invalid_index() -> bool:
    row = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE c.relname = :name AND NOT i.indisvalid"
        ),
        {"name": INDEX_NAME},
    )
    return row.first() is not None


def upgrade() -> None:
    if not _is_postgresql():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # CONCURRENTLY cannot run inside a transaction, and a plain build
    # would block writes to product. Leave Alembic's transaction for it.
    with op.get_context().autocommit_block():
        # A failed concurrent build leaves an invalid index behind under
        # this name while Alembic stays at 0008; remove it so a retry
        # does not fail on the name clash. Valid indexes are kept.
        if not op.get_context().as_sql and _has_invalid_index():
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
        op.create_index(
            op.f(INDEX_NAME),
            "product",
            ["name"],
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    if not _is_postgresql():
        return
    # IF EXISTS so a partly applied or hand-repaired database can still
    # move backward.
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
