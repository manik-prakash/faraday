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
