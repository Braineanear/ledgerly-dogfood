"""Run the stock recompute once a night at a fixed UTC time.

Opt-in entry point: ``python -m ledgerly_worker.scheduler``. The clock,
the wait and the job are all injected, so tests can drive the loop with
a fake clock and never sleep.
"""

import logging
import os
import re
import signal
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from ledgerly_worker import recompute

logger = logging.getLogger("ledgerly_worker.scheduler")

DEFAULT_HOUR = 2
DEFAULT_MINUTE = 0

# A wait shorter than this is rounded up, so a clock that is a fraction
# of a microsecond short of the target cannot cause a busy loop.
MIN_WAIT_SECONDS = 0.05

_TIME_PATTERN = re.compile(r"^(\d{2}):(\d{2})$")


def next_run_after(now: datetime, hour: int, minute: int) -> datetime:
    """Return the next daily ``hour:minute`` UTC strictly after ``now``.

    ``now`` must be timezone-aware; it is converted to UTC first.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = now.astimezone(UTC)
    candidate = current.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate


def parse_run_time(value: str) -> tuple[int, int]:
    """Parse an ``HH:MM`` string into ``(hour, minute)``."""
    match = _TIME_PATTERN.match(value.strip())
    if match is None:
        raise ValueError(f"expected HH:MM, got {value!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        raise ValueError(f"time out of range: {value!r}")
    return hour, minute


def _run_job(job: Callable[[], int | None]) -> None:
    """Run the job once; log failures and never raise."""
    try:
        code = job()
    except Exception:
        logger.exception("nightly job raised; will try again tomorrow")
        return
    if code:
        logger.error(
            "nightly job exited with code %s; will try again tomorrow",
            code,
        )
    else:
        logger.info("nightly job finished")


def run_nightly(
    job: Callable[[], int | None],
    now: Callable[[], datetime],
    wait: Callable[[float], object],
    stop: Callable[[], bool],
    hour: int = DEFAULT_HOUR,
    minute: int = DEFAULT_MINUTE,
    max_runs: int | None = None,
) -> int:
    """Run ``job`` every day at ``hour:minute`` UTC; return the run count.

    ``now`` returns a timezone-aware datetime. ``wait(seconds)`` blocks
    for up to that long and returns truthy when a stop was requested,
    like ``threading.Event.wait``. ``stop()`` reports the same flag.

    The job does not run on startup. A job that raises or returns a
    non-zero code is logged and the loop carries on. After a run the
    next slot is taken from the current clock, so a slot that passed
    during a long job or downtime is skipped and no slot runs twice.
    A stop that arrives during a job takes effect once the job returns.
    """
    runs = 0
    target = next_run_after(now(), hour, minute)
    while max_runs is None or runs < max_runs:
        if stop():
            break
        current = now()
        if current < target:
            seconds = (target - current).total_seconds()
            if wait(max(seconds, MIN_WAIT_SECONDS)):
                break
            continue
        logger.info("running nightly job for slot %s", target.isoformat())
        _run_job(job)
        runs += 1
        target = next_run_after(now(), hour, minute)
    return runs


def _default_job() -> int:
    return recompute.main([])


def main(
    argv: Sequence[str] | None = None,
    *,
    install_signals: bool = True,
    now: Callable[[], datetime] | None = None,
    wait: Callable[[float], object] | None = None,
    job: Callable[[], int | None] | None = None,
    max_runs: int | None = None,
) -> int:
    """Run the nightly scheduler until SIGINT or SIGTERM arrives.

    ``RECOMPUTE_AT`` (``HH:MM`` UTC, default 02:00) sets the run time.
    Configuration is checked before the first wait. Exit codes: 0 after
    a clean stop, 2 for an invalid ``RECOMPUTE_AT`` or, with the default
    job, a missing ``DATABASE_URL``. ``now``, ``wait``, ``job`` and
    ``max_runs`` are test hooks.
    """
    if argv:
        print("scheduler takes no arguments", file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO)

    raw = os.environ.get("RECOMPUTE_AT", "").strip()
    try:
        hour, minute = (
            parse_run_time(raw)
            if raw
            else (DEFAULT_HOUR, DEFAULT_MINUTE)
        )
    except ValueError as exc:
        print(f"scheduler failed: invalid RECOMPUTE_AT: {exc}", file=sys.stderr)
        return 2
    if job is None:
        if not os.environ.get("DATABASE_URL"):
            print(
                "scheduler failed: DATABASE_URL is not set",
                file=sys.stderr,
            )
            return 2
        job = _default_job

    stop = threading.Event()
    previous: dict[int, object] = {}

    def handle(signum: int, frame: object) -> None:
        stop.set()

    try:
        if install_signals:
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous[signum] = signal.signal(signum, handle)
        logger.info("nightly recompute scheduled at %02d:%02d UTC", hour, minute)
        run_nightly(
            job,
            now or (lambda: datetime.now(UTC)),
            wait or stop.wait,
            stop.is_set,
            hour=hour,
            minute=minute,
            max_runs=max_runs,
        )
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
