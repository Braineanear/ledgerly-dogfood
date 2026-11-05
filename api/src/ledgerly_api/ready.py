"""Readiness probe: GET /ready checks the database and Redis."""

import logging
import math
import socket
import ssl
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from ledgerly_api.auth import load_url_settings
from ledgerly_api.db import get_database_url
from ledgerly_api.problems import problem_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Seconds allowed for each dependency; read at call time.
CHECK_TIMEOUT = 2.0

DEFAULT_REDIS_PORT = 6379
MAX_REPLY_BYTES = 4096

# One worker, so a hung probe can block at most one thread.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ready-db")
_lock = threading.Lock()
_inflight: Future[None] | None = None


class ProbeBusy(Exception):
    """A previous database probe is still running."""


class RedisCheckError(Exception):
    """Redis did not answer as expected."""


def _select_one() -> None:
    """Run SELECT 1 on a dedicated, unpooled engine and dispose it."""
    url = get_database_url()
    connect_args: dict[str, float | int] = {}
    if url.startswith("sqlite"):
        connect_args["timeout"] = CHECK_TIMEOUT
    elif url.startswith("postgres"):
        connect_args["connect_timeout"] = max(1, math.ceil(CHECK_TIMEOUT))
    engine = create_engine(url, poolclass=NullPool, connect_args=connect_args)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def check_database() -> None:
    """Probe the database within CHECK_TIMEOUT or raise.

    The probe cannot be cancelled once started. While an earlier probe is
    still running, this fails at once instead of queueing more work.
    """
    global _inflight
    with _lock:
        if _inflight is not None and not _inflight.done():
            raise ProbeBusy("previous database probe is still running")
        future = _executor.submit(_select_one)
        _inflight = future
    future.result(timeout=CHECK_TIMEOUT)


def _command(*args: str) -> bytes:
    """Encode a Redis command as a RESP array of bulk strings."""
    parts = [f"*{len(args)}\r\n".encode()]
    for arg in args:
        data = arg.encode()
        parts.append(f"${len(data)}\r\n".encode() + data + b"\r\n")
    return b"".join(parts)


def _expect(sock: socket.socket, reader, command: tuple[str, ...], reply: bytes):
    sock.sendall(_command(*command))
    line = reader.readline(MAX_REPLY_BYTES)
    if line.rstrip(b"\r\n") != reply:
        raise RedisCheckError("unexpected reply")


def check_redis(url: str) -> None:
    """PING Redis at url, or raise. Supports redis://, rediss://, AUTH, SELECT."""
    parsed = urlparse(url)
    if parsed.scheme not in ("redis", "rediss"):
        raise RedisCheckError("unsupported scheme")
    host = parsed.hostname
    if not host:
        raise RedisCheckError("missing host")
    port = parsed.port or DEFAULT_REDIS_PORT
    sock = socket.create_connection((host, port), timeout=CHECK_TIMEOUT)
    try:
        if parsed.scheme == "rediss":
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=host
            )
        sock.settimeout(CHECK_TIMEOUT)
        reader = sock.makefile("rb")
        if parsed.password:
            auth = ("AUTH", unquote(parsed.password))
            if parsed.username:
                auth = ("AUTH", unquote(parsed.username), unquote(parsed.password))
            _expect(sock, reader, auth, b"+OK")
        database = parsed.path.lstrip("/")
        if database.isdigit():
            _expect(sock, reader, ("SELECT", database), b"+OK")
        _expect(sock, reader, ("PING",), b"+PONG")
    finally:
        sock.close()


def _unavailable(request: Request, dependency: str, exc: Exception) -> JSONResponse:
    # Only the dependency and exception class are logged: exception text can
    # carry connection URLs and passwords.
    logger.warning(
        "Readiness check failed: dependency=%s error=%s",
        dependency,
        type(exc).__name__,
    )
    return problem_response(
        request,
        503,
        f"{dependency.capitalize()} is unavailable.",
        title="Service Unavailable",
        extra={"dependency": dependency},
    )


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    """Answer 200 when dependencies respond, else 503 naming the first failure."""
    try:
        check_database()
    except Exception as exc:  # noqa: BLE001 - any probe failure means not ready
        return _unavailable(request, "database", exc)
    try:
        check_redis(load_url_settings().redis_url)
    except Exception as exc:  # noqa: BLE001 - any probe failure means not ready
        return _unavailable(request, "redis", exc)
    return JSONResponse({"status": "ready"})
