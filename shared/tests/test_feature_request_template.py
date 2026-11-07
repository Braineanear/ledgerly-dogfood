"""Check the feature request issue form is structurally sound."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml"
TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}
OPTIONS = ["api", "worker", "shared", "web", "infra", "other"]


def _text() -> str:
    return FORM.read_text(encoding="utf-8")


def _items() -> dict[str, str]:
    """Map each body item id to its block of text."""
    parts = re.split(r"^  - type:", _text(), flags=re.MULTILINE)[1:]
    items = {}
    for part in parts:
        found = re.search(r"^    id: (\S+)$", part, flags=re.MULTILINE)
        if found:
            items[found.group(1)] = part
    return items


@pytest.mark.parametrize("key", ["name", "description", "body"])
def test_top_level_keys(key):
    assert re.search(rf"^{key}:", _text(), flags=re.MULTILINE)


def test_labels_contain_enhancement():
    match = re.search(r"^labels:\s*\[(.*)\]\s*$", _text(), flags=re.MULTILINE)
    assert match, "labels line missing"
    labels = [item.strip() for item in match.group(1).split(",")]
    assert "enhancement" in labels


def test_no_tabs():
    assert "\t" not in _text()


def test_types_valid():
    types = re.findall(r"^  - type: (\S+)$", _text(), flags=re.MULTILINE)
    assert types
    assert set(types) <= TYPES


def test_ids_unique():
    ids = re.findall(r"^    id: (\S+)$", _text(), flags=re.MULTILINE)
    assert len(ids) == len(set(ids))


def test_component_dropdown():
    block = _items()["component"]
    assert block.strip().startswith("dropdown")
    options = re.findall(r"^        - (\S+)$", block, flags=re.MULTILINE)
    assert options == OPTIONS
    assert re.search(
        r"^    validations:\n      required: true$", block, flags=re.MULTILINE
    )


@pytest.mark.parametrize("item_id", ["problem", "proposed-solution"])
def test_required_textareas(item_id):
    block = _items()[item_id]
    assert block.strip().startswith("textarea")
    assert re.search(
        r"^    validations:\n      required: true$", block, flags=re.MULTILINE
    )


@pytest.mark.parametrize("item_id", ["alternatives", "additional-context"])
def test_optional_textareas(item_id):
    block = _items()[item_id]
    assert block.strip().startswith("textarea")
    assert "required: true" not in block


def test_optional_textareas_have_labels_and_descriptions():
    items = _items()
    for item_id in ("alternatives", "additional-context"):
        block = items[item_id]
        assert re.search(r"^\s+label:", block, flags=re.MULTILINE)
        assert re.search(r"^\s+description:", block, flags=re.MULTILINE)


def test_missing_item_lookup_returns_none():
    assert _items().get("nonexistent-id") is None

