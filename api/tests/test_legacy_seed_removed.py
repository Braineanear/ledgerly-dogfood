"""Tests verifying the legacy seed script has been removed."""

import importlib
import importlib.util
from pathlib import Path


def test_legacy_seed_script_is_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    legacy_seed_path = root / "scripts" / "legacy_seed.py"
    assert not legacy_seed_path.exists()


def test_legacy_seed_cannot_be_imported() -> None:
    root = Path(__file__).resolve().parents[2]
    legacy_seed_path = root / "scripts" / "legacy_seed.py"
    spec = importlib.util.spec_from_file_location("legacy_seed", legacy_seed_path)
    assert spec is None or spec.loader is None or not legacy_seed_path.exists()


def test_active_seed_module_remains_available() -> None:
    seed_module = importlib.import_module("ledgerly_api.seed")
    assert hasattr(seed_module, "seed")
    assert hasattr(seed_module, "main")
