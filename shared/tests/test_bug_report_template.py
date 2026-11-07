"""Check the structure of the bug report issue form as plain text."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
MAKEFILE = ROOT / "Makefile"
TYPES = {"markdown", "input", "textarea", "dropdown", "checkboxes"}
OPTIONS = ["api", "worker", "shared", "web", "infra", "other"]


def _text() -> str:
    return FORM.read_text(encoding="utf-8")


def _items() -> list[str]:
    body = _text().partition("\nbody:\n")[2]
    return re.split(r"^  - (?=type:)", body, flags=re.MULTILINE)[1:]


def _item(item_id: str) -> str:
    for item in _items():
        if re.search(rf"^    id: {re.escape(item_id)}$", item, re.MULTILINE):
            return item
    raise AssertionError(f"missing item with id '{item_id}'")


def test_top_level_keys_at_column_zero():
    text = _text()
    for key in ("name:", "description:", "body:"):
        assert re.search(rf"^{key}", text, re.MULTILINE), f"missing {key}"


def test_title_attribute():
    assert re.search(
        r'^title: "\[Bug\]: "$', _text(), re.MULTILINE
    ), "missing or malformed title prefix"


def test_labels_contain_bug():
    assert re.search(r"^labels: \[.*\bbug\b.*\]$", _text(), re.MULTILINE)


def test_no_tabs():
    assert "\t" not in _text()


def test_types_are_valid():
    types = re.findall(r"^\s*(?:- )?type: (\S+)$", _text(), re.MULTILINE)
    assert types
    assert set(types) <= TYPES


def test_ids_are_unique():
    ids = re.findall(r"^\s+id: (\S+)$", _text(), re.MULTILINE)
    assert ids
    assert len(ids) == len(set(ids))


def test_component_dropdown_options_and_required():
    block = _item("component")
    assert re.search(r"^type: dropdown$", block, re.MULTILINE)
    options = re.findall(r"^        - (\S+)$", block, re.MULTILINE)
    assert options == OPTIONS
    assert re.search(
        r"^    validations:\n      required: true$", block, re.MULTILINE
    )


def test_required_textareas():
    for item_id in ("what-happened", "expected-behaviour", "reproduction-steps"):
        block = _item(item_id)
        assert re.search(r"^type: textarea$", block, re.MULTILINE)
        assert re.search(
            r"^    validations:\n      required: true$", block, re.MULTILINE
        ), f"{item_id} is not required"


@pytest.mark.parametrize(
    "item_id,expected_type",
    [
        ("version", "input"),
        ("environment", "textarea"),
        ("logs", "textarea"),
    ],
)
def test_optional_fields_exist_and_not_required(item_id, expected_type):
    block = _item(item_id)
    assert re.search(rf"^type: {expected_type}$", block, re.MULTILINE)
    assert "required: true" not in block, f"{item_id} should not be required"


def test_logs_field_renders_shell():
    block = _item("logs")
    assert re.search(r"^      render: shell$", block, re.MULTILINE)


def test_missing_item_raises_assertion_error():
    with pytest.raises(AssertionError, match="missing item with id 'nonexistent'"):
        _item("nonexistent")


def test_markdown_item_mentions_secrets():
    markdown = [i for i in _items() if i.startswith("type: markdown")]
    assert markdown
    assert any("secrets" in item for item in markdown)


def test_pr_template_and_makefile_consistency():
    assert PR_TEMPLATE.exists(), "PULL_REQUEST_TEMPLATE.md missing"
    pr_text = PR_TEMPLATE.read_text(encoding="utf-8")
    assert "## Summary" in pr_text
    assert "Closes #" in pr_text
    assert "## Components touched" in pr_text
    assert "## Testing" in pr_text
    assert "## Checklist" in pr_text
    assert "CI runs only `make test`" in pr_text

    makefile_text = MAKEFILE.read_text(encoding="utf-8")
    make_targets = set(
        re.findall(r"^([a-zA-Z0-9_-]+):", makefile_text, re.MULTILINE)
    )

    referenced_targets = re.findall(r"`make ([a-zA-Z0-9_-]+)`", pr_text)
    assert referenced_targets, "PR template references no make targets"
    for target in referenced_targets:
        assert (
            target in make_targets
        ), f"PR template names unknown make target: {target}"

