"""Integration check: the scripted agent satisfies every DataWrangle-Bench grader.

No Docker — the file-match / json-field graders run host-side, so this exercises
the whole non-container path: task.yaml is valid, a solver exists, and its output
passes the real grader.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from bench.grading import run_grader
from bench.grading.base import GraderContext
from bench.spec import load_task

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "agents" / "scripted-agent"))
solve = pytest.importorskip("solve")

TASK_DIRS = sorted((REPO / "evals" / "datawrangle-mini" / "tasks").iterdir())


def _build_workspace(tmp_path: Path, spec, task_dir: Path) -> Path:
    ws = tmp_path / "workspace"
    (ws / "input").mkdir(parents=True)
    (ws / "output").mkdir(parents=True)
    for f in spec.files:
        dest = ws / "input" / f.dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(task_dir / f.src, dest)
    return ws


@pytest.mark.parametrize("task_dir", TASK_DIRS, ids=lambda p: p.name)
def test_scripted_agent_passes_datawrangle_task(task_dir: Path, tmp_path: Path) -> None:
    spec, tdir = load_task(task_dir)
    ws = _build_workspace(tmp_path, spec, tdir)

    solve.solve(ws, spec.id)

    outcome = run_grader(spec.grader, GraderContext(workspace=ws, task_dir=tdir))
    assert outcome.passed, f"{spec.id}: {outcome.detail}"


def test_every_datawrangle_task_has_a_solver() -> None:
    ids = {load_task(d)[0].id for d in TASK_DIRS}
    missing = ids - set(solve.FILE_SOLVERS)
    assert not missing, f"no scripted solver for: {sorted(missing)}"
