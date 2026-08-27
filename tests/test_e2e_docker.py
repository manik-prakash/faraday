"""End-to-end runs against real Docker containers.

Deselected by default (`-m "not docker"`); run with a Docker daemon available to
exercise the container plumbing the unit tests can only fake: script-exit grading
inside the live task-env container, image build/pull, artifact capture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

docker = pytest.importorskip("docker")

pytestmark = pytest.mark.docker

REPO = Path(__file__).resolve().parent.parent
SCRIPTED = REPO / "agents" / "scripted-agent"


@pytest.fixture(scope="module")
def runner():
    from faraday.exceptions import DockerUnavailable
    from faraday.orchestrator.runner import LocalRunner

    try:
        return LocalRunner(REPO)
    except DockerUnavailable as e:
        pytest.skip(f"Docker not available: {e}")


def test_file_match_task_passes(runner, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FARADAY_RUNS_DIR", str(tmp_path))
    result, run_dir = runner.run(
        REPO / "evals" / "shell-mini" / "tasks" / "t001-hello", SCRIPTED
    )
    assert result.status == "passed", result.detail
    assert result.score == 1.0
    assert (run_dir / "output" / "trajectory.jsonl").is_file()


def test_script_exit_task_passes(runner, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FARADAY_RUNS_DIR", str(tmp_path))
    result, _ = runner.run(
        REPO / "evals" / "shell-mini" / "tasks" / "t003-dedupe", SCRIPTED
    )
    assert result.status == "passed", result.detail


def test_script_exit_failure_is_clean_not_error(runner, tmp_path, monkeypatch) -> None:
    # dummy-agent doesn't solve t003, so the grader script exits non-zero:
    # the run must land in `failed`, not `error`, with the script tail in detail.
    monkeypatch.setenv("FARADAY_RUNS_DIR", str(tmp_path))
    result, _ = runner.run(
        REPO / "evals" / "shell-mini" / "tasks" / "t003-dedupe",
        REPO / "agents" / "dummy-agent",
    )
    assert result.status in {"failed", "agent_error"}
    assert result.status != "error"


def test_datawrangle_task_passes(runner, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FARADAY_RUNS_DIR", str(tmp_path))
    result, _ = runner.run(
        REPO / "evals" / "datawrangle-mini" / "tasks" / "d006-join", SCRIPTED
    )
    assert result.status == "passed", result.detail
