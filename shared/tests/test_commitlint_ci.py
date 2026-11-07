import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "commitlint.config.mjs"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def _commitlint_job():
    text = _workflow_text()
    start = text.index("  commitlint:")
    rest = text[start + len("  commitlint:"):]
    match = re.search(r"^  [A-Za-z0-9_-]+:\s*$", rest, re.MULTILINE)
    return rest[: match.start()] if match else rest


def test_config_extends_conventional():
    text = CONFIG.read_text(encoding="utf-8")
    assert "export default" in text
    assert "@commitlint/config-conventional" in text


def test_no_root_node_manifest_or_lockfile():
    for name in (
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
    ):
        assert not (ROOT / name).exists(), name


def test_commitlint_job_runs_on_pull_requests_only():
    job = _commitlint_job()
    assert "if: github.event_name == 'pull_request'" in job


def test_commitlint_job_fetches_full_history():
    assert "fetch-depth: 0" in _commitlint_job()


def test_commitlint_job_pins_packages():
    job = _commitlint_job()
    assert "npx" in job
    assert re.search(r"@commitlint/cli@\d+\.\d+\.\d+", job)
    assert re.search(
        r"@commitlint/config-conventional@\d+\.\d+\.\d+", job
    )


def test_commitlint_job_installs_in_repo_and_uses_range():
    job = _commitlint_job()
    assert "NODE_PATH" not in job
    assert "--prefix" not in job
    assert "npx --no-install commitlint" in job
    assert "github.event.pull_request.base.sha" in job
    assert "github.event.pull_request.head.sha" in job


def test_contributing_documents_commitlint_job():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "CI / commitlint" in text
    assert "Conventional Commits" in text
    assert "not a\nrequired check until a maintainer enables it" in text
    assert "single job" not in text


def _pinned_version():
    match = re.search(r"@commitlint/cli@(\d+\.\d+\.\d+)", _commitlint_job())
    return match.group(1)


def test_commitlint_runs_with_repo_config(tmp_path):
    if not (shutil.which("node") and shutil.which("npm")):
        pytest.skip("node and npm are not available")
    shutil.copy(CONFIG, tmp_path / CONFIG.name)
    version = _pinned_version()
    install = subprocess.run(
        [
            "npm",
            "install",
            "--no-save",
            "--no-package-lock",
            f"@commitlint/cli@{version}",
            f"@commitlint/config-conventional@{version}",
        ],
        check=False,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    if install.returncode != 0:
        pytest.skip("commitlint packages could not be installed")

    def lint(message):
        return subprocess.run(
            ["npx", "--no-install", "commitlint"],
            check=False,
            cwd=tmp_path,
            input=message,
            capture_output=True,
            text=True,
        )

    assert lint("feat: add export\n").returncode == 0
    assert lint("Add foo\n").returncode != 0


def test_workflow_still_runs_make_test():
    assert "make test" in _workflow_text()
