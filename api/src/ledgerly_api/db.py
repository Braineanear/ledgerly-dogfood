"""Database engine and per-request session handling. Part of Ledgerly."""

from collections.abc import Iterator
from functools import cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from ledgerly_api.auth import load_url_settings


def get_database_url() -> str:
    """Return DATABASE_URL, read at call time; there is no default."""
    return load_url_settings().database_url


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
