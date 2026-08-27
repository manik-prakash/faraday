"""The outsider path, end to end: bring an eval (zip) + an agent (prebuilt image).

Deselected by default; needs a Docker daemon. Mirrors docs/byo-quickstart.md.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

docker = pytest.importorskip("docker")
pytestmark = pytest.mark.docker

REPO = Path(__file__).resolve().parent.parent

_UPLOADED_TASK = """\
id: byo001-echo
name: Echo OK
instruction: Write the text ok to output/answer.txt.
grader:
  type: file-match
  path: output/answer.txt
  expect: "ok"
"""

_AGENT_WRITES_OK = (
    "import pathlib;"
    "p=pathlib.Path('/task/output');p.mkdir(parents=True,exist_ok=True);"
    "(p/'answer.txt').write_text('ok')"
)


@pytest.fixture(scope="module")
def runner():
    from bench.exceptions import DockerUnavailable
    from bench.orchestrator.runner import LocalRunner

    try:
        return LocalRunner(REPO)
    except DockerUnavailable as e:
        pytest.skip(f"Docker not available: {e}")


def _write_agent(dir_: Path, entrypoint: list[str]) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "agent.yaml").write_text(
        "id: byo-agent\nname: BYO Agent\n"
        "image: python:3.12-slim\n"
        f"entrypoint: {json.dumps(entrypoint)}\n",
        encoding="utf-8",
    )
    return dir_


def test_byo_eval_zip_plus_prebuilt_image_agent_scores(runner, tmp_path, monkeypatch) -> None:
    from bench.evals_io import install_eval_archive

    # 1. bring an eval as a zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("tasks/byo001-echo/task.yaml", _UPLOADED_TASK)
    evals_root = tmp_path / "evals"
    ids = install_eval_archive(buf.getvalue(), "byo-demo", evals_root)
    assert ids == ["byo001-echo"]

    # 2. bring an agent by prebuilt image (no build context)
    agent_dir = _write_agent(tmp_path / "agent", ["python", "-c", _AGENT_WRITES_OK])

    # 3. run it
    monkeypatch.setenv("BENCH_RUNS_DIR", str(tmp_path / "runs"))
    result, _ = runner.run(evals_root / "byo-demo" / "tasks" / "byo001-echo", agent_dir)
    assert result.status == "passed", result.detail
    assert result.score == 1.0
    assert result.meta["images"]["agent"] == "python:3.12-slim"  # used as-is, not built


def test_broken_byo_agent_fails_legibly(runner, tmp_path, monkeypatch) -> None:
    from bench.evals_io import install_eval_archive

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("tasks/byo001-echo/task.yaml", _UPLOADED_TASK)
    evals_root = tmp_path / "evals"
    install_eval_archive(buf.getvalue(), "byo-demo", evals_root)

    agent_dir = _write_agent(tmp_path / "agent", ["python", "-c", "raise SystemExit(3)"])

    monkeypatch.setenv("BENCH_RUNS_DIR", str(tmp_path / "runs"))
    result, _ = runner.run(evals_root / "byo-demo" / "tasks" / "byo001-echo", agent_dir)
    assert result.status in {"agent_error", "failed"}
    assert result.status != "error"
    assert "3" in result.detail  # exit code surfaced, not a stack trace
    assert "Traceback" not in result.detail
