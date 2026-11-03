"""Database engine and per-request session handling."""

import os
from collections.abc import Iterator
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

DEFAULT_DATABASE_URL = "sqlite:///./ledgerly.db"


def get_database_url() -> str:
    """Return DATABASE_URL, read at call time, or the SQLite default."""
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


@cache
def _engine_for(url: str) -> Engine:
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, connect_args=connect_args)


def get_engine() -> Engine:
    """Return the engine for the current DATABASE_URL, created lazily."""
    return _engine_for(get_database_url())


def get_session() -> Iterator[Session]:
    """Yield a session for one request and close it afterwards."""
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()
