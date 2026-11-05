"""Fail when docs/architecture.md names a module that no longer exists."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
DOC = ROOT / "docs" / "architecture.md"
COMPONENTS = ["api", "worker", "shared", "web"]
TOKEN = re.compile(r"`([^`\s]+)`")
SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")


def _sections() -> dict[str, str]:
    text = DOC.read_text(encoding="utf-8")
    sections = {}
    for part in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = part.partition("\n")
        sections[title.strip()] = body
    return sections


def _paths(body: str) -> list[str]:
    return [
        token
        for token in TOKEN.findall(body)
        if "/" in token and token.endswith(SUFFIXES)
    ]


@pytest.mark.parametrize("component", COMPONENTS)
def test_section_names_existing_modules(component):
    sections = _sections()
    assert component in sections, f"missing section '## {component}'"
    paths = _paths(sections[component])
    assert paths, f"section '{component}' names no module paths"
    for path in paths:
        resolved = (ROOT / path).resolve()
        assert not Path(path).is_absolute() and resolved.is_relative_to(
            ROOT.resolve()
        ), f"section '{component}' names path outside repo: {path}"
        assert resolved.is_file(), (
            f"section '{component}' names missing file: {path}"
        )


@pytest.mark.parametrize("component", COMPONENTS)
def test_module_paths_belong_to_component(component):
    sections = _sections()
    assert component in sections, f"missing section '## {component}'"
    paths = _paths(sections[component])
    for path in paths:
        assert path.startswith(f"{component}/"), (
            f"path '{path}' in section '{component}' does not start with '{component}/'"
        )


def test_validation_fails_for_nonexistent_module():
    fake_path = "api/src/ledgerly_api/nonexistent_module_xyz.py"
    assert not (ROOT / fake_path).exists()
    fake_doc_body = f"- `{fake_path}`: non-existent module."
    paths = _paths(fake_doc_body)
    assert fake_path in paths
    resolved = (ROOT / fake_path).resolve()
    assert not resolved.is_file()


def test_paths_extractor_handles_js_and_jsx():
    sample = "- `web/src/index.js`: entry\n- `web/src/App.jsx`: root component"
    paths = _paths(sample)
    assert "web/src/index.js" in paths
    assert "web/src/App.jsx" in paths

