"""Recompute StockLevel rows from stock movements, once, then exit."""

import argparse
import logging
import os
import sys
from collections.abc import Sequence

from ledgerly_shared import StockInvariantError, recompute_stock_levels
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

logger = logging.getLogger("ledgerly_worker.recompute")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the recompute and return the exit code.

    Exit codes: 0 success, 1 negative stock total (nothing written),
    2 DATABASE_URL is not set.
    """
    parser = argparse.ArgumentParser(
        prog="ledgerly_worker.recompute",
        description="Rebuild StockLevel quantities from stock movements.",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="only recompute this tenant (default: every tenant)",
    )
    args = parser.parse_args(argv)

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("recompute failed: DATABASE_URL is not set", file=sys.stderr)
        return 2

    logging.basicConfig(level=logging.INFO)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url)
    try:
        with Session(engine) as session:
            try:
                count = recompute_stock_levels(session, args.tenant_id)
                session.commit()
            except StockInvariantError as exc:
                session.rollback()
                print(f"recompute failed: {exc}", file=sys.stderr)
                return 1
    finally:
        engine.dispose()
    logger.info("recomputed stock levels: %d rows written", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
