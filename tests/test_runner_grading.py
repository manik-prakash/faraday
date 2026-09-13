"""LocalRunner's grader-context wiring and crash-safety."""

from __future__ import annotations

from pathlib import Path

from faraday.orchestrator.runner import LocalRunner
from faraday.spec import TaskSpec


class _FakeClient:
    pass


def _runner() -> LocalRunner:
    r = object.__new__(LocalRunner)
    r.client = _FakeClient()
    return r


def _spec(timeout_s: int = 300) -> TaskSpec:
    return TaskSpec.model_validate(
        {
            "id": "t001-hello",
            "name": "x",
            "instruction": "go",
            "grader": {"type": "file-match", "path": "output/r.txt", "expect": "1"},
            "limits": {"timeout_s": timeout_s},
        }
    )


def test_grader_context_uses_the_tasks_configured_timeout(tmp_path: Path) -> None:
    runner = _runner()
    ctx = runner._grader_context(_spec(timeout_s=175), tmp_path, tmp_path, task_container=None)
    assert ctx.timeout_s == 175


def test_grade_safely_survives_an_unexpected_exception(monkeypatch, tmp_path: Path) -> None:
    from faraday.grading.base import GraderContext
    from faraday.orchestrator import runner as runner_mod

    def _boom(grader_spec, ctx):
        raise RuntimeError("container vanished mid-grade")

    monkeypatch.setattr(runner_mod, "run_grader", _boom)

    ctx = GraderContext(workspace=tmp_path, task_dir=tmp_path)
    outcome = runner_mod._grade_safely(object(), ctx)

    assert outcome.passed is False
    assert outcome.score == 0.0
    assert "RuntimeError" in outcome.detail


def test_grade_safely_passes_through_a_normal_outcome(tmp_path: Path) -> None:
    from faraday.grading.base import GraderContext
    from faraday.orchestrator.runner import _grade_safely
    from faraday.spec import FileMatchGrader

    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "r.txt").write_text("ok", encoding="utf-8")
    ctx = GraderContext(workspace=tmp_path, task_dir=tmp_path)
    grader_spec = FileMatchGrader(type="file-match", path="output/r.txt", expect="ok")

    outcome = _grade_safely(grader_spec, ctx)

    assert outcome.passed is True
