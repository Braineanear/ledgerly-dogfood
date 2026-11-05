"""Executable placeholder for the Ledgerly worker."""

import signal
import threading
import time
from collections.abc import Callable, Sequence

from ledgerly_shared import PlaceholderModel


def process_once() -> None:
    """Do one unit of work; the stub processes nothing."""


def run(
    should_stop: Callable[[], bool],
    sleep: Callable[[float], object] = time.sleep,
    interval: float = 1.0,
    max_iterations: int | None = None,
) -> int:
    """Loop until stopped or capped and return the iteration count."""
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        if should_stop():
            break
        process_once()
        iterations += 1
        sleep(interval)
    return iterations


def main(
    argv: Sequence[str] | None = None,
    *,
    sleep: Callable[[float], object] | None = None,
    install_signals: bool = True,
) -> int:
    """Run the placeholder worker until SIGINT or SIGTERM arrives.

    ``sleep`` is a test hook; by default the loop waits on the stop flag
    so it wakes promptly when a signal arrives.
    """
    PlaceholderModel(identifier="worker")
    stop = threading.Event()
    previous: dict[int, object] = {}

    def handle(signum: int, frame: object) -> None:
        stop.set()

    try:
        if install_signals:
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous[signum] = signal.signal(signum, handle)
        run(stop.is_set, sleep=sleep or stop.wait)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
