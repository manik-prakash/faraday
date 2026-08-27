"""The scripted agent satisfies every host-side shell-mini grader (no Docker).

``script-exit`` tasks need a live container and are covered by the Docker E2E
test instead; here we check the ``file-match`` / ``json-field`` ones.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from conftest import load_agent_solver

from faraday.grading import run_grader
from faraday.grading.base import GraderContext
from faraday.spec import load_task

REPO = Path(__file__).resolve().parent.parent
solve = load_agent_solver("scripted-agent")

HOST_GRADED = sorted(
    d
    for d in (REPO / "evals" / "shell-mini" / "tasks").iterdir()
    if load_task(d)[0].grader.type in {"file-match", "file-regex", "json-field"}
)


@pytest.mark.parametrize("task_dir", HOST_GRADED, ids=lambda p: p.name)
def test_scripted_agent_passes_shell_task(task_dir: Path, tmp_path: Path) -> None:
    spec, tdir = load_task(task_dir)
    ws = tmp_path / "workspace"
    (ws / "input").mkdir(parents=True)
    (ws / "output").mkdir(parents=True)
    for f in spec.files:
        dest = ws / "input" / f.dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tdir / f.src, dest)

    solve.solve(ws, spec.id)

    outcome = run_grader(spec.grader, GraderContext(workspace=ws, task_dir=tdir))
    assert outcome.passed, f"{spec.id}: {outcome.detail}"
