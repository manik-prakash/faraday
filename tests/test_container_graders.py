"""Tests for the script-exit grader that runs inside the task-env container."""

from __future__ import annotations

from pathlib import Path

from bench.grading.base import GraderContext
from bench.grading.container_graders import ScriptExitGrader_
from bench.spec import ScriptExitGrader


def _ctx(tmp_path: Path, **kw) -> GraderContext:
    ws = tmp_path / "workspace"
    (ws / "output").mkdir(parents=True, exist_ok=True)
    return GraderContext(workspace=ws, task_dir=tmp_path, **kw)


def test_missing_script_returns_clean_failure(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, task_container=object())
    outcome = ScriptExitGrader_(ScriptExitGrader(type="script-exit", script="grader.sh")).grade(ctx)
    assert outcome.passed is False
    assert outcome.score == 0.0
    assert "grader script missing" in outcome.detail


def test_no_task_container_returns_clean_failure(tmp_path: Path) -> None:
    # script-exit needs a live container; when there is none it must fail
    # gracefully rather than raising AttributeError on None.
    (tmp_path / "grader.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    ctx = _ctx(tmp_path, task_container=None)
    outcome = ScriptExitGrader_(ScriptExitGrader(type="script-exit", script="grader.sh")).grade(ctx)
    assert outcome.passed is False
    assert outcome.score == 0.0
    assert "container" in outcome.detail.lower()


class _RecordingContainer:
    def exec_run(self, *a, **kw):
        class R:
            exit_code = 0
            output = (b"", b"")

        return R()


def test_crlf_grader_script_is_normalised_to_lf(tmp_path: Path) -> None:
    # a grader.sh authored on Windows (CRLF) must still run: `bash` chokes on
    # `set -euo pipefail\r`. The staged copy must have no carriage returns.
    (tmp_path / "grader.sh").write_bytes(b"#!/usr/bin/env bash\r\nset -euo pipefail\r\nexit 0\r\n")
    ctx = _ctx(tmp_path, task_container=_RecordingContainer())

    ScriptExitGrader_(ScriptExitGrader(type="script-exit", script="grader.sh")).grade(ctx)

    staged = (ctx.workspace / ".bench-grader" / "grader.sh").read_bytes()
    assert b"\r" not in staged
