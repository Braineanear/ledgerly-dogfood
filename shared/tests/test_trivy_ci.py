import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
IMAGE = "ledgerly-api:ci"


def _workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def _trivy_job():
    text = _workflow_text()
    start = text.index("  trivy:")
    rest = text[start + len("  trivy:"):]
    match = re.search(r"^  [A-Za-z0-9_-]+:\s*$", rest, re.MULTILINE)
    return rest[: match.start()] if match else rest


def test_workflow_has_one_pinned_trivy_action():
    text = _workflow_text()
    assert text.count("aquasecurity/trivy-action@") == 1
    assert re.search(
        r"aquasecurity/trivy-action@v\d+\.\d+\.\d+\s", text
    )
    assert "@latest" not in text
    assert "@master" not in text


def test_trivy_job_scans_the_built_api_image():
    job = _trivy_job()
    assert "aquasecurity/trivy-action@" in job
    assert f"docker build -f api/Dockerfile -t {IMAGE} ." in job
    assert re.search(
        rf"image-ref:\s*{re.escape(IMAGE)}\s*$", job, re.MULTILINE
    )


def test_trivy_job_policy():
    job = _trivy_job()
    assert re.search(r"severity:\s*HIGH,CRITICAL\s*$", job, re.MULTILINE)
    assert re.search(r"exit-code:\s*[\"']?1[\"']?\s*$", job, re.MULTILINE)
    assert re.search(r"ignore-unfixed:\s*true\s*$", job, re.MULTILINE)


def test_trivy_job_has_no_write_permissions():
    job = _trivy_job()
    assert "contents: read" in job
    assert "write" not in job
    assert "security-events" not in job


def test_workflow_still_runs_make_test():
    assert "make test" in _workflow_text()
