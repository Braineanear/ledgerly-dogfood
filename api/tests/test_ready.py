"""Tests for the GET /ready readiness probe."""

import shutil
import socket
import ssl
import subprocess
import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from ledgerly_api import ready
from ledgerly_api.main import app, create_app

SECRET = "postgresql://ledger:hunter2@db.internal/ledgerly"


@pytest.fixture(autouse=True)
def clean_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> Iterator[None]:
    """Use a temporary sqlite database and a dummy Redis URL."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ready.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(ready, "_inflight", None)
    yield


@pytest.fixture
def stub_redis(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the Redis probe with a recorder that always passes."""
    seen: list[str] = []
    monkeypatch.setattr(ready, "check_redis", seen.append)
    return seen


def _assert_problem(response, dependency: str) -> None:
    assert response.status_code == 503
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    body = response.json()
    assert body["status"] == 503
    assert body["dependency"] == dependency


@pytest.mark.usefixtures("stub_redis")
@pytest.mark.parametrize("make_app", [create_app, lambda: app])
def test_ready_returns_200_when_database_answers(make_app) -> None:
    with TestClient(make_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.usefixtures("stub_redis")
def test_ready_names_failing_database_without_leaking_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken() -> None:
        raise OperationalError("SELECT 1", {}, Exception(f"cannot reach {SECRET}"))

    monkeypatch.setattr(ready, "_select_one", broken)

    with TestClient(create_app()) as client:
        response = client.get("/ready")

    _assert_problem(response, "database")
    assert "hunter2" not in response.text
    assert "db.internal" not in response.text


@pytest.mark.usefixtures("stub_redis")
def test_blocked_database_times_out_and_bounds_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    calls: list[int] = []

    def blocked() -> None:
        calls.append(1)
        release.wait(timeout=30)

    monkeypatch.setattr(ready, "_select_one", blocked)
    monkeypatch.setattr(ready, "CHECK_TIMEOUT", 0.2)

    try:
        with TestClient(create_app()) as client:
            started = time.monotonic()
            first = client.get("/ready")
            assert time.monotonic() - started < 1.5
            _assert_problem(first, "database")

            started = time.monotonic()
            second = client.get("/ready")
            assert time.monotonic() - started < 1.5
            _assert_problem(second, "database")

            assert len(calls) == 1
    finally:
        release.set()
        stuck = ready._inflight
        if stuck is not None:
            stuck.result(timeout=5)

    monkeypatch.setattr(ready, "_select_one", lambda: None)
    with TestClient(create_app()) as client:
        assert client.get("/ready").status_code == 200


def test_redis_failure_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://:topsecret@cache.internal:6379")

    def broken(url: str) -> None:
        raise ready.RedisCheckError(url)

    monkeypatch.setattr(ready, "check_redis", broken)

    with TestClient(create_app()) as client:
        response = client.get("/ready")

    _assert_problem(response, "redis")
    assert "topsecret" not in response.text


def test_redis_passing_returns_200(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    seen: list[str] = []
    monkeypatch.setattr(ready, "check_redis", seen.append)

    with TestClient(create_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert seen == ["redis://localhost:6379"]


def test_redis_is_always_probed(stub_redis: list[str]) -> None:
    with TestClient(create_app()) as client:
        assert client.get("/ready").status_code == 200

    assert stub_redis == ["redis://localhost:6379/0"]


class FakeRedis:
    """A tiny threaded RESP server that records the commands it receives."""

    def __init__(self, auth: list[str] | None = None) -> None:
        self.auth = auth
        self.commands: list[list[str]] = []
        self._server = socket.socket()
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(5)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.close()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _read_command(self, reader) -> list[str] | None:
        header = reader.readline()
        if not header.startswith(b"*"):
            return None
        args = []
        for _ in range(int(header[1:])):
            size = int(reader.readline()[1:])
            args.append(reader.read(size + 2)[:-2].decode())
        return args

    def _handle(self, conn: socket.socket) -> None:
        authed = self.auth is None
        with conn, conn.makefile("rb") as reader:
            while (command := self._read_command(reader)) is not None:
                self.commands.append(command)
                if command[0] == "AUTH":
                    authed = command[1:] == self.auth
                    reply = b"+OK\r\n" if authed else b"-WRONGPASS\r\n"
                elif not authed:
                    reply = b"-NOAUTH Authentication required.\r\n"
                elif command[0] == "PING":
                    reply = b"+PONG\r\n"
                else:
                    reply = b"+OK\r\n"
                conn.sendall(reply)


@pytest.fixture
def fake_redis_factory() -> Iterator:
    servers: list[FakeRedis] = []

    def make(auth: list[str] | None = None) -> FakeRedis:
        server = FakeRedis(auth)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_check_redis_plain_ping(fake_redis_factory) -> None:
    server = fake_redis_factory()

    ready.check_redis(f"redis://127.0.0.1:{server.port}")

    assert server.commands == [["PING"]]


def test_check_redis_password_auth(fake_redis_factory) -> None:
    server = fake_redis_factory(auth=["pw"])

    ready.check_redis(f"redis://:pw@127.0.0.1:{server.port}")

    assert server.commands == [["AUTH", "pw"], ["PING"]]


def test_check_redis_fails_without_required_auth(fake_redis_factory) -> None:
    server = fake_redis_factory(auth=["pw"])

    with pytest.raises(ready.RedisCheckError):
        ready.check_redis(f"redis://127.0.0.1:{server.port}")


def test_check_redis_fails_with_wrong_password(fake_redis_factory) -> None:
    server = fake_redis_factory(auth=["pw"])

    with pytest.raises(ready.RedisCheckError):
        ready.check_redis(f"redis://:nope@127.0.0.1:{server.port}")


def test_check_redis_user_and_password_auth(fake_redis_factory) -> None:
    server = fake_redis_factory(auth=["bob", "p w"])

    ready.check_redis(f"redis://bob:p%20w@127.0.0.1:{server.port}")

    assert server.commands == [["AUTH", "bob", "p w"], ["PING"]]


def test_check_redis_selects_database(fake_redis_factory) -> None:
    server = fake_redis_factory()

    ready.check_redis(f"redis://127.0.0.1:{server.port}/2")

    assert server.commands == [["SELECT", "2"], ["PING"]]


def test_check_redis_closed_port_raises() -> None:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    with pytest.raises(OSError):
        ready.check_redis(f"redis://127.0.0.1:{port}")


def test_check_redis_rejects_other_schemes() -> None:
    with pytest.raises(ready.RedisCheckError):
        ready.check_redis("http://127.0.0.1:6379")


def test_check_redis_tls_only_for_rediss(
    monkeypatch: pytest.MonkeyPatch, fake_redis_factory
) -> None:
    server = fake_redis_factory()
    hostnames: list[str] = []

    class FakeContext:
        def wrap_socket(self, sock, server_hostname=None):
            hostnames.append(server_hostname)
            return sock

    monkeypatch.setattr(ready.ssl, "create_default_context", FakeContext)

    ready.check_redis(f"redis://127.0.0.1:{server.port}")
    assert hostnames == []

    ready.check_redis(f"rediss://127.0.0.1:{server.port}")
    assert hostnames == ["127.0.0.1"]


def test_check_redis_tls_handshake_is_real_and_verified(
    monkeypatch: pytest.MonkeyPatch, fake_redis_factory
) -> None:
    """A real handshake with a non-TLS server fails; hostname is passed."""
    server = fake_redis_factory()
    monkeypatch.setattr(ready, "CHECK_TIMEOUT", 0.5)
    real_create = ready.ssl.create_default_context
    seen: list[tuple[str | None, int]] = []

    def spy_context():
        context = real_create()
        real_wrap = context.wrap_socket

        def wrap(sock, server_hostname=None, **kwargs):
            seen.append((server_hostname, context.verify_mode))
            return real_wrap(sock, server_hostname=server_hostname, **kwargs)

        return type("Spy", (), {"wrap_socket": staticmethod(wrap)})()

    monkeypatch.setattr(ready.ssl, "create_default_context", spy_context)

    started = time.monotonic()
    with pytest.raises(OSError):
        ready.check_redis(f"rediss://127.0.0.1:{server.port}")

    assert time.monotonic() - started < 3
    assert seen == [("127.0.0.1", ready.ssl.CERT_REQUIRED)]
    assert server.commands == []


class TlsFakeRedis(FakeRedis):
    """FakeRedis that speaks TLS with the given certificate."""

    def __init__(self, certfile: str, keyfile: str) -> None:
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(certfile, keyfile)
        super().__init__()

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn = self.context.wrap_socket(conn, server_side=True)
        except OSError:
            conn.close()
            return
        super()._handle(conn)


@pytest.fixture
def tls_cert(tmp_path) -> tuple[str, str]:
    """A self-signed certificate valid for 127.0.0.1, made with openssl."""
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is not available to make a test certificate")
    cert = str(tmp_path / "cert.pem")
    key = str(tmp_path / "key.pem")
    subprocess.run(
        [
            openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", key, "-out", cert, "-days", "1",
            "-subj", "/CN=127.0.0.1",
            "-addext", "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


def test_check_redis_tls_trusted_certificate_succeeds(
    monkeypatch: pytest.MonkeyPatch, tls_cert
) -> None:
    cert, key = tls_cert
    server = TlsFakeRedis(cert, key)
    try:
        real_create = ssl.create_default_context

        def trusting():
            context = real_create()
            context.load_verify_locations(cert)
            return context

        monkeypatch.setattr(ready.ssl, "create_default_context", trusting)

        ready.check_redis(f"rediss://127.0.0.1:{server.port}")

        assert server.commands == [["PING"]]
    finally:
        server.close()


def test_check_redis_tls_untrusted_certificate_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tls_cert
) -> None:
    cert, key = tls_cert
    server = TlsFakeRedis(cert, key)
    try:
        monkeypatch.setattr(ready, "CHECK_TIMEOUT", 2.0)

        with pytest.raises(ssl.SSLError):
            ready.check_redis(f"rediss://127.0.0.1:{server.port}")

        assert server.commands == []
    finally:
        server.close()


def test_check_redis_tls_wrong_hostname_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tls_cert
) -> None:
    cert, key = tls_cert
    server = TlsFakeRedis(cert, key)
    try:
        real_create = ssl.create_default_context

        def trusting():
            context = real_create()
            context.load_verify_locations(cert)
            return context

        monkeypatch.setattr(ready.ssl, "create_default_context", trusting)

        # localhost is not in the certificate's subject alternative names.
        with pytest.raises(ssl.SSLError):
            ready.check_redis(f"rediss://localhost:{server.port}")

        assert server.commands == []
    finally:
        server.close()


def test_check_redis_silent_server_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(5)
    monkeypatch.setattr(ready, "CHECK_TIMEOUT", 0.3)

    try:
        started = time.monotonic()
        with pytest.raises(OSError):
            ready.check_redis(f"redis://127.0.0.1:{silent.getsockname()[1]}")
        assert time.monotonic() - started < 3
    finally:
        silent.close()


def test_probe_engine_uses_unpooled_sqlite_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}
    real_create = ready.create_engine

    def spy(url, **kwargs):
        captured.update(kwargs)
        return real_create(url, **kwargs)

    monkeypatch.setattr(ready, "create_engine", spy)
    monkeypatch.setattr(ready, "CHECK_TIMEOUT", 2.0)

    ready._select_one()

    assert captured["poolclass"] is ready.NullPool
    assert captured["connect_args"] == {"timeout": 2.0}


def test_probe_engine_sets_postgres_connect_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", SECRET)
    captured: dict = {}
    disposed: list[bool] = []

    class FakeEngine:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception("down"))

        def dispose(self) -> None:
            disposed.append(True)

    def fake_create(url, **kwargs):
        captured.update(kwargs)
        return FakeEngine()

    monkeypatch.setattr(ready, "create_engine", fake_create)

    with pytest.raises(OperationalError):
        ready._select_one()

    assert captured["poolclass"] is ready.NullPool
    assert captured["connect_args"] == {"connect_timeout": 2}
    assert disposed == [True]


@pytest.mark.usefixtures("stub_redis")
def test_unreachable_database_returns_503_quickly(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    missing = tmp_path / "no" / "such" / "dir" / "ready.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing}")

    with TestClient(create_app()) as client:
        started = time.monotonic()
        response = client.get("/ready")

    assert time.monotonic() - started < 3
    _assert_problem(response, "database")
    assert str(missing) not in response.text
