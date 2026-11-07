"""Tests for the nightly scheduler, driven by a fake clock."""

import logging
import os
import signal
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest
from ledgerly_shared.orm import (
    Base,
    Product,
    StockLevel,
    StockMovement,
    Tenant,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ledgerly_worker import scheduler


def at(day, hour=0, minute=0, month=1, year=2025):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


class FakeClock:
    """A tz-aware clock whose wait advances time instead of sleeping."""

    def __init__(self, start, stop_on_wait=None):
        self.current = start
        self.stopped = False
        self.stop_on_wait = stop_on_wait
        self.waits = []

    def now(self):
        return self.current

    def advance(self, delta):
        self.current += delta

    def stop(self):
        self.stopped = True

    def is_stopped(self):
        return self.stopped

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.stop_on_wait == len(self.waits):
            self.stopped = True
        if self.stopped:
            return True
        self.current += timedelta(seconds=seconds)
        return False


class Recorder:
    """A job that records the clock time of every run."""

    def __init__(self, clock, results=()):
        self.clock = clock
        self.results = list(results)
        self.times = []

    def __call__(self):
        self.times.append(self.clock.now())
        if not self.results:
            return 0
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def run(clock, job, **kwargs):
    return scheduler.run_nightly(
        job, clock.now, clock.wait, clock.is_stopped, **kwargs
    )


def test_job_runs_at_two_exactly_once():
    clock = FakeClock(at(1, 1))
    job = Recorder(clock)
    assert run(clock, job, max_runs=1) == 1
    assert job.times == [at(1, 2)]
    assert sum(clock.waits) == pytest.approx(3600, abs=1)


def test_three_days_give_three_runs():
    clock = FakeClock(at(1, 0))
    job = Recorder(clock)
    assert run(clock, job, max_runs=3) == 3
    assert job.times == [at(1, 2), at(2, 2), at(3, 2)]


def test_missed_slot_is_skipped():
    clock = FakeClock(at(1, 1))
    times = []

    def slow_job():
        times.append(clock.now())
        if len(times) == 1:
            clock.advance(timedelta(hours=30))

    run(clock, slow_job, max_runs=2)
    assert times == [at(1, 2), at(3, 2)]


def test_startup_after_slot_waits_for_next_day():
    clock = FakeClock(at(1, 3))
    job = Recorder(clock)
    assert run(clock, job, max_runs=1) == 1
    assert job.times == [at(2, 2)]


@pytest.mark.parametrize("failure", [1, RuntimeError("boom")])
def test_failure_is_logged_and_next_night_runs(failure, caplog):
    clock = FakeClock(at(1, 0))
    job = Recorder(clock, results=[failure, 0])
    with caplog.at_level(logging.INFO, logger=scheduler.logger.name):
        assert run(clock, job, max_runs=2) == 2
    assert job.times == [at(1, 2), at(2, 2)]
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1


def test_stop_during_wait_skips_job():
    clock = FakeClock(at(1, 0), stop_on_wait=1)
    job = Recorder(clock)
    assert run(clock, job) == 0
    assert job.times == []


def test_stop_before_start_skips_job():
    clock = FakeClock(at(1, 0))
    clock.stop()
    job = Recorder(clock)
    assert run(clock, job) == 0
    assert job.times == []


def test_custom_time_is_used():
    clock = FakeClock(at(1, 0))
    job = Recorder(clock)
    run(clock, job, hour=5, minute=30, max_runs=1)
    assert job.times == [at(1, 5, 30)]


def test_fractional_time_before_slot_waits_bounded_and_runs_once():
    # One microsecond short of the slot: the wait must be rounded up to
    # the minimum, not 1e-6 seconds, and the job must still run once.
    start = at(1, 2) - timedelta(microseconds=1)
    clock = FakeClock(start)
    job = Recorder(clock)
    assert run(clock, job, max_runs=1) == 1
    expected = start + timedelta(seconds=scheduler.MIN_WAIT_SECONDS)
    assert job.times == [expected]
    assert clock.waits == [scheduler.MIN_WAIT_SECONDS]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (at(1, 1), at(1, 2)),
        (at(1, 2), at(2, 2)),
        (at(1, 3), at(2, 2)),
        (at(31, 3), at(1, 2, month=2)),
        (at(28, 3, month=2), at(1, 2, month=3)),
        (at(28, 3, month=2, year=2024), at(29, 2, month=2, year=2024)),
        (at(31, 3, month=12), at(1, 2, year=2026)),
    ],
)
def test_next_run_after_boundaries(now, expected):
    assert scheduler.next_run_after(now, 2, 0) == expected


def test_next_run_after_converts_to_utc():
    plus_two = timezone(timedelta(hours=2))
    now = datetime(2025, 1, 1, 3, 30, tzinfo=plus_two)
    assert scheduler.next_run_after(now, 2, 0) == at(1, 2)


def test_next_run_after_rejects_naive_datetime():
    with pytest.raises(ValueError):
        scheduler.next_run_after(datetime(2025, 1, 1), 2, 0)


@pytest.mark.parametrize("value", ["2am", "24:00", "02:60", "2:00", "x"])
def test_invalid_recompute_at_exits_2(value, monkeypatch, capsys):
    monkeypatch.setenv("RECOMPUTE_AT", value)
    code = scheduler.main(install_signals=False, job=lambda: 0)
    assert code == 2
    assert "RECOMPUTE_AT" in capsys.readouterr().err


def test_missing_database_url_exits_2_before_waiting(
    monkeypatch, capsys
):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RECOMPUTE_AT", raising=False)
    clock = FakeClock(at(1, 0))
    code = scheduler.main(
        install_signals=False, now=clock.now, wait=clock.wait
    )
    assert code == 2
    assert clock.waits == []
    assert "DATABASE_URL" in capsys.readouterr().err


def test_main_uses_recompute_at(monkeypatch):
    monkeypatch.setenv("RECOMPUTE_AT", "04:15")
    clock = FakeClock(at(1, 0))
    job = Recorder(clock)
    code = scheduler.main(
        install_signals=False,
        now=clock.now,
        wait=clock.wait,
        job=job,
        max_runs=1,
    )
    assert code == 0
    assert job.times == [at(1, 4, 15)]


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'stock.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        tenant = Tenant(name="Acme")
        session.add(tenant)
        session.flush()
        product = Product(
            tenant_id=tenant.id,
            sku="SKU-1",
            name="Widget",
            price_minor=100,
            currency="USD",
        )
        session.add(product)
        session.flush()
        for warehouse, delta in (("a", 5), ("a", 3), ("b", 2)):
            session.add(
                StockMovement(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    warehouse=warehouse,
                    delta=delta,
                )
            )
    engine.dispose()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("RECOMPUTE_AT", raising=False)
    return url


def test_default_job_runs_recompute_through_scheduler(db_url):
    clock = FakeClock(at(1, 0))
    code = scheduler.main(
        install_signals=False,
        now=clock.now,
        wait=clock.wait,
        max_runs=1,
    )
    assert code == 0
    engine = create_engine(db_url)
    with Session(engine) as session:
        rows = session.execute(
            select(StockLevel.warehouse, StockLevel.quantity)
        ).all()
    engine.dispose()
    assert {row[0]: row[1] for row in rows} == {"a": 8, "b": 2}


CHILD = textwrap.dedent(
    """
    import os
    import sys
    import time
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from ledgerly_worker import scheduler

    marker_dir = Path(os.environ["SCHEDULER_STUB_JOB_DIR"])
    calls = []


    def stub():
        n = len(list(marker_dir.glob("started-*"))) + 1
        (marker_dir / f"started-{n}").write_text("")
        time.sleep(1.0)
        (marker_dir / f"done-{n}").write_text("")


    def fake_now():
        calls.append(1)
        start = datetime(2025, 1, 1, tzinfo=UTC)
        if len(calls) == 1:
            return start
        days = len(calls) - 2
        return start + timedelta(hours=3, days=days)


    sys.exit(
        scheduler.main(
            install_signals=True, job=stub, now=fake_now
        )
    )
    """
)


@pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX signals"
)
def test_sigterm_during_job_finishes_job_and_exits_0(tmp_path):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("RECOMPUTE_AT", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["SCHEDULER_STUB_JOB_DIR"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started-1").exists():
            assert proc.poll() is None, "child exited early"
            assert time.monotonic() < deadline, "job never started"
            time.sleep(0.02)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
        assert (tmp_path / "done-1").exists()
        assert not (tmp_path / "started-2").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


CHILD_WAIT = textwrap.dedent(
    """
    import os
    import sys
    import time
    from datetime import UTC, datetime
    from pathlib import Path

    from ledgerly_worker import scheduler

    marker_dir = Path(os.environ["SCHEDULER_STUB_JOB_DIR"])


    def stub():
        (marker_dir / "started-1").write_text("")


    def fake_now():
        (marker_dir / "waiting-1").write_text("")
        return datetime(2025, 1, 1, 1, 0, tzinfo=UTC)


    sys.exit(
        scheduler.main(
            install_signals=True, job=stub, now=fake_now
        )
    )
    """
)


CHILD_FAILING_JOB = textwrap.dedent(
    """
    import os
    import sys
    import time
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from ledgerly_worker import scheduler

    marker_dir = Path(os.environ["SCHEDULER_STUB_JOB_DIR"])
    calls = []


    def stub():
        n = len(list(marker_dir.glob("started-*"))) + 1
        (marker_dir / f"started-{n}").write_text("")
        time.sleep(1.0)
        raise RuntimeError("simulated job failure")


    def fake_now():
        calls.append(1)
        start = datetime(2025, 1, 1, tzinfo=UTC)
        if len(calls) == 1:
            return start
        days = len(calls) - 2
        return start + timedelta(hours=3, days=days)


    sys.exit(
        scheduler.main(
            install_signals=True, job=stub, now=fake_now
        )
    )
    """
)


@pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX signals"
)
def test_sigint_during_job_finishes_job_and_exits_0(tmp_path):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("RECOMPUTE_AT", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["SCHEDULER_STUB_JOB_DIR"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started-1").exists():
            assert proc.poll() is None, "child exited early"
            assert time.monotonic() < deadline, "job never started"
            time.sleep(0.02)
        proc.send_signal(signal.SIGINT)
        assert proc.wait(timeout=10) == 0
        assert (tmp_path / "done-1").exists()
        assert not (tmp_path / "started-2").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX signals"
)
def test_sigterm_during_wait_exits_without_running_job(tmp_path):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("RECOMPUTE_AT", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["SCHEDULER_STUB_JOB_DIR"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD_WAIT],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "waiting-1").exists():
            assert proc.poll() is None, "child exited early"
            assert time.monotonic() < deadline, "wait never reached"
            time.sleep(0.02)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
        assert not (tmp_path / "started-1").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX signals"
)
def test_sigterm_during_failing_job_exits_0(tmp_path):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("RECOMPUTE_AT", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["SCHEDULER_STUB_JOB_DIR"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD_FAILING_JOB],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started-1").exists():
            assert proc.poll() is None, "child exited early"
            assert time.monotonic() < deadline, "job never started"
            time.sleep(0.02)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=10) == 0
        assert not (tmp_path / "started-2").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.mark.skipif(
    sys.platform == "win32", reason="needs POSIX signals"
)
def test_multiple_signals_during_job_finishes_job_and_exits_0(tmp_path):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("RECOMPUTE_AT", None)
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["SCHEDULER_STUB_JOB_DIR"] = str(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, "-c", CHILD],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "started-1").exists():
            assert proc.poll() is None, "child exited early"
            assert time.monotonic() < deadline, "job never started"
            time.sleep(0.02)
        proc.send_signal(signal.SIGTERM)
        time.sleep(0.05)
        proc.send_signal(signal.SIGINT)
        assert proc.wait(timeout=10) == 0
        assert (tmp_path / "done-1").exists()
        assert not (tmp_path / "started-2").exists()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_signal_handlers_restored_after_main():
    orig_sigint = signal.getsignal(signal.SIGINT)
    orig_sigterm = signal.getsignal(signal.SIGTERM)
    clock = FakeClock(at(1, 0))
    clock.stop()
    code = scheduler.main(
        install_signals=True,
        now=clock.now,
        wait=clock.wait,
        job=lambda: 0,
    )
    assert code == 0
    assert signal.getsignal(signal.SIGINT) == orig_sigint
    assert signal.getsignal(signal.SIGTERM) == orig_sigterm

