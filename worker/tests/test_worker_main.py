from ledgerly_shared import PlaceholderModel

from ledgerly_worker.main import main


def test_main_returns_success_without_processing_jobs() -> None:
    assert PlaceholderModel(identifier="worker").identifier == "worker"
    assert main() == 0
