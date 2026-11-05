import signal

import pytest
from ledgerly_shared import PlaceholderModel

from ledgerly_worker import main as worker_main
from ledgerly_worker.main import main, run

GUARD_LIMIT = 100


class Recorder:
    """Fake sleep that records calls and fails instead of hanging."""

    def __init__(self, on_call=None) -> None:
        self.calls: list[float] = []
        self.on_call = on_call

    def __call__(self, interval: float) -> None:
        self.calls.append(interval)
        if len(self.calls) > GUARD_LIMIT:
            raise AssertionError("loop did not stop")
        if self.on_call is not None:
            self.on_call(len(self.calls))


@pytest.fixture
def process_calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(
        worker_main, "process_once", lambda: calls.append(1)
    )
    return calls


def test_placeholder_model_is_shared() -> None:
    assert PlaceholderModel(identifier="worker").identifier == "worker"


def test_run_honours_max_iterations(process_calls: list[int]) -> None:
    sleep = Recorder()
    assert run(lambda: False, sleep=sleep, interval=0.5, max_iterations=3) == 3
    assert len(process_calls) == 3
    assert sleep.calls == [0.5, 0.5, 0.5]


def test_run_single_iteration_sleeps_once(process_calls: list[int]) -> None:
    sleep = Recorder()
    assert run(lambda: False, sleep=sleep, max_iterations=1) == 1
    assert len(process_calls) == 1
    assert len(sleep.calls) == 1


def test_run_zero_iterations_does_no_work(process_calls: list[int]) -> None:
    sleep = Recorder()
    assert run(lambda: False, sleep=sleep, max_iterations=0) == 0
    assert process_calls == []
    assert sleep.calls == []


def test_run_preset_stop_does_no_work(process_calls: list[int]) -> None:
    sleep = Recorder()
    assert run(lambda: True, sleep=sleep) == 0
    assert process_calls == []
    assert sleep.calls == []


def test_run_stops_when_should_stop_turns_true(
    process_calls: list[int],
) -> None:
    sleep = Recorder()
    checks = []

    def should_stop() -> bool:
        checks.append(1)
        return len(checks) > 4

    assert run(should_stop, sleep=sleep) == 4
    assert len(process_calls) == 4
    assert len(sleep.calls) == 4


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_main_loops_until_signalled_then_returns_zero(
    signum: signal.Signals, process_calls: list[int]
) -> None:
    original_int = signal.getsignal(signal.SIGINT)
    original_term = signal.getsignal(signal.SIGTERM)

    def on_call(count: int) -> None:
        if count == 2:
            signal.raise_signal(signum)

    sleep = Recorder(on_call)
    assert main(sleep=sleep) == 0
    assert len(sleep.calls) == 2
    assert len(process_calls) == 2
    assert signal.getsignal(signal.SIGINT) is original_int
    assert signal.getsignal(signal.SIGTERM) is original_term
