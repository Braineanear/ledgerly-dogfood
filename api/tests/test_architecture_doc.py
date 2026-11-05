"""Check that modules named in docs/architecture.md still exist."""

import re
from pathlib import Path, PurePath

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "architecture.md"
COMPONENTS = ("api", "worker", "shared", "web")
ENTRY = re.compile(r"^- Module: `([^`]+)`", re.MULTILINE)


def validate_module_path(root, section, rel):
    """Return an error string for a bad module entry, else None."""
    if not rel.strip():
        return "empty module path"
    path = PurePath(rel)
    if path.is_absolute() or rel.startswith("/"):
        return f"absolute module path: {rel}"
    if ".." in path.parts:
        return f"module path contains '..': {rel}"
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return f"module path escapes the repo root: {rel}"
    if not resolved.exists():
        return f"missing module: {rel}"
    if path.parts[0] != section:
        return f"module {rel} is not under component {section}"
    return None


def split_sections(text):
    sections = {}
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    for part in parts[1:]:
        name, _, body = part.partition("\n")
        sections[name.strip()] = body
    return sections


def test_documented_modules_exist():
    sections = split_sections(DOC.read_text(encoding="utf-8"))
    errors = []
    for component in COMPONENTS:
        assert component in sections, f"missing section: {component}"
        entries = ENTRY.findall(sections[component])
        assert entries, f"no module entries in section: {component}"
        for rel in entries:
            error = validate_module_path(ROOT, component, rel)
            if error:
                errors.append(error)
    assert not errors, "\n".join(errors)


def test_backticks_only_in_module_entries():
    stray = [
        line
        for line in DOC.read_text(encoding="utf-8").splitlines()
        if "`" in line and not ENTRY.match(line)
    ]
    assert not stray, f"backticks outside module entries: {stray}"


def test_missing_path_reported(tmp_path):
    (tmp_path / "api").mkdir()
    error = validate_module_path(tmp_path, "api", "api/gone.py")
    assert error and "missing" in error


def test_existing_path_accepted(tmp_path):
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "a.py").write_text("")
    assert validate_module_path(tmp_path, "api", "api/a.py") is None


@pytest.mark.parametrize("rel", ["api/../x", "/etc/passwd", ""])
def test_unsafe_paths_rejected(tmp_path, rel):
    assert validate_module_path(tmp_path, "api", rel) is not None


def test_wrong_component_rejected(tmp_path):
    (tmp_path / "web").mkdir()
    error = validate_module_path(tmp_path, "api", "web")
    assert error and "not under component" in error
