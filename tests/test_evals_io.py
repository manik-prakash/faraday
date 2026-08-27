"""Tests for BYO-eval archive install + task-registry sync."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from bench.evals_io import (
    install_eval_archive,
    iter_task_dirs,
    pack_eval_dir,
    sync_task_registry,
)
from bench.exceptions import SpecError

REPO = Path(__file__).resolve().parent.parent

_TASK_YAML = """\
id: {tid}
name: Uploaded {tid}
instruction: write output/answer.txt
grader:
  type: file-match
  path: output/answer.txt
  expect: "ok"
"""


def _zip(members: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_install_valid_archive_returns_task_ids(tmp_path: Path) -> None:
    data = _zip(
        {
            "tasks/u001-a/task.yaml": _TASK_YAML.format(tid="u001-a"),
            "tasks/u002-b/task.yaml": _TASK_YAML.format(tid="u002-b"),
        }
    )
    ids = install_eval_archive(data, "myeval", tmp_path)
    assert sorted(ids) == ["u001-a", "u002-b"]
    assert (tmp_path / "myeval" / "tasks" / "u001-a" / "task.yaml").is_file()


def test_install_rejects_path_traversal(tmp_path: Path) -> None:
    data = _zip({"../evil.txt": "x", "tasks/u001-a/task.yaml": _TASK_YAML.format(tid="u001-a")})
    with pytest.raises(SpecError):
        install_eval_archive(data, "myeval", tmp_path)
    assert not (tmp_path / "myeval").exists()  # nothing left behind


def test_install_rejects_archive_with_no_tasks(tmp_path: Path) -> None:
    with pytest.raises(SpecError):
        install_eval_archive(_zip({"readme.md": "hi"}), "myeval", tmp_path)


def test_install_rejects_invalid_task_spec(tmp_path: Path) -> None:
    data = _zip({"tasks/u001-a/task.yaml": "id: u001-a\nname: broken\n"})  # no instruction/grader
    with pytest.raises(SpecError):
        install_eval_archive(data, "myeval", tmp_path)
    assert not (tmp_path / "myeval").exists()


def test_install_rejects_bad_eval_name(tmp_path: Path) -> None:
    data = _zip({"tasks/u001-a/task.yaml": _TASK_YAML.format(tid="u001-a")})
    with pytest.raises(SpecError):
        install_eval_archive(data, "../hax", tmp_path)


_SCRIPT_TASK = """\
id: {tid}
name: script {tid}
instruction: do it
grader:
  type: script-exit
  script: grader.sh
"""


def test_uploaded_script_graders_rejected_by_default(tmp_path: Path) -> None:
    data = _zip(
        {
            "tasks/u001-a/task.yaml": _SCRIPT_TASK.format(tid="u001-a"),
            "tasks/u001-a/grader.sh": "#!/usr/bin/env bash\nexit 0\n",
        }
    )
    with pytest.raises(SpecError) as exc:
        install_eval_archive(data, "myeval", tmp_path)
    assert "script" in str(exc.value).lower() and "u001-a" in str(exc.value)
    assert not (tmp_path / "myeval").exists()


def test_uploaded_script_graders_allowed_when_opted_in(tmp_path: Path) -> None:
    data = _zip(
        {
            "tasks/u001-a/task.yaml": _SCRIPT_TASK.format(tid="u001-a"),
            "tasks/u001-a/grader.sh": "#!/usr/bin/env bash\nexit 0\n",
        }
    )
    ids = install_eval_archive(data, "myeval", tmp_path, allow_script_graders=True)
    assert ids == ["u001-a"]


def test_invalid_task_error_names_the_task_dir(tmp_path: Path) -> None:
    data = _zip({"tasks/u007-broken/task.yaml": "id: u007-broken\nname: x\n"})
    with pytest.raises(SpecError) as exc:
        install_eval_archive(data, "myeval", tmp_path)
    assert "u007-broken" in str(exc.value)


def test_pack_eval_dir_roundtrips_through_install(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "tasks" / "u001-a").mkdir(parents=True)
    (src / "tasks" / "u001-a" / "task.yaml").write_text(_TASK_YAML.format(tid="u001-a"), "utf-8")

    ids = install_eval_archive(pack_eval_dir(src), "packed", tmp_path / "out")
    assert ids == ["u001-a"]


def test_iter_task_dirs_finds_repo_evals() -> None:
    names = {d.name for d in iter_task_dirs(REPO / "evals")}
    assert {"t001-hello", "g001-periodic-count", "d001-select-columns"} <= names


def test_sync_task_registry_upserts_rows(fresh_db) -> None:
    from bench.store.db import Task

    SessionLocal = fresh_db
    with SessionLocal() as session:
        n1 = sync_task_registry(session, REPO / "evals")
        session.commit()
        n2 = sync_task_registry(session, REPO / "evals")  # idempotent
        session.commit()
        count = session.query(Task).count()

    assert n1 >= 40  # 15 shell + 15 gaia + 10 datawrangle
    assert count == n1
    assert n2 == 0  # second sync adds nothing
