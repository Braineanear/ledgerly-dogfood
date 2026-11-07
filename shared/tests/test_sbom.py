import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
MAKEFILE = ROOT / "Makefile"
GITIGNORE = ROOT / ".gitignore"

needs_make = pytest.mark.skipif(
    shutil.which("make") is None, reason="make is not available"
)


def _workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def _sbom_step():
    text = _workflow_text()
    start = text.index("anchore/sbom-action@")
    # The step starts at the "- uses:" line that holds the action.
    start = text.rfind("\n", 0, start) + 1
    return text[start:]


def test_workflow_has_one_pinned_sbom_action():
    text = _workflow_text()
    assert text.count("anchore/sbom-action@") == 1
    assert re.search(r"anchore/sbom-action@v\d+\.\d+\.\d+\s", text)
    assert "@latest" not in text


def test_sbom_step_is_api_only():
    assert "if: matrix.image == 'api'" in _sbom_step()


def test_sbom_step_scans_pushed_image():
    step = _sbom_step()
    assert "env.IMAGE_NAME" in step
    assert "github.ref_name" in step
    assert "format: spdx-json" in step


def test_sbom_step_uploads_artifact():
    assert "upload-artifact: true" in _sbom_step()


def test_workflow_permissions_unchanged():
    text = _workflow_text()
    assert "contents: write" not in text
    assert "contents: read" in text
    assert "packages: write" in text


def test_makefile_phony_and_verify():
    text = MAKEFILE.read_text(encoding="utf-8")
    phony = re.search(r"^\.PHONY:(.*)$", text, re.MULTILINE).group(1)
    assert "sbom" in phony.split()
    verify = re.search(r"^verify:(.*)$", text, re.MULTILINE).group(1)
    assert "sbom" not in verify.split()


def test_gitignore_covers_sbom_output():
    lines = GITIGNORE.read_text(encoding="utf-8").splitlines()
    assert "sbom-*.spdx.json" in lines


def _make_sbom(cwd, *args):
    shutil.copy(MAKEFILE, cwd / "Makefile")
    return subprocess.run(
        ["make", "sbom", *args],
        check=False,
        cwd=cwd,
        capture_output=True,
        text=True,
    )


@needs_make
def test_make_sbom_skips_without_syft(tmp_path):
    result = _make_sbom(tmp_path, "SYFT=definitely-not-installed")
    assert result.returncode == 0
    assert "skipping" in result.stdout
    assert not (tmp_path / "sbom-api.spdx.json").exists()


def _fake_tool(path, log):
    path.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> "{log}"\n'
        'if [ "$1" = "scan" ]; then touch sbom-api.spdx.json; fi\n',
        encoding="utf-8",
    )
    path.chmod(0o755)


@needs_make
def test_make_sbom_builds_and_scans_api_image(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    docker_log = tmp_path / "docker.log"
    syft_log = tmp_path / "syft.log"
    docker = bin_dir / "docker"
    syft = bin_dir / "syft"
    _fake_tool(docker, docker_log)
    _fake_tool(syft, syft_log)

    result = _make_sbom(
        work,
        f"SYFT={syft}",
        f"DOCKER={docker}",
        "API_IMAGE=test:img",
    )

    assert result.returncode == 0, result.stderr
    assert (
        docker_log.read_text(encoding="utf-8").strip()
        == "build -f api/Dockerfile -t test:img ."
    )
    assert (
        syft_log.read_text(encoding="utf-8").strip()
        == "scan test:img -o spdx-json=sbom-api.spdx.json"
    )
    assert (work / "sbom-api.spdx.json").exists()
