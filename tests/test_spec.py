"""Tests for task.yaml / agent.yaml parsing and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from bench.exceptions import SpecError
from bench.spec import (
    AgentManifest,
    FileMatchGrader,
    JsonFieldGrader,
    ScriptExitGrader,
    TaskSpec,
    load_task,
)


def _task_yaml(**overrides: str) -> dict:
    base = {
        "id": "t001-hello",
        "name": "Hello",
        "instruction": "do the thing",
        "grader": {"type": "file-match", "path": "output/report.txt", "expect": "42"},
    }
    base.update(overrides)
    return base


def test_minimal_task_spec_parses_with_defaults() -> None:
    spec = TaskSpec.model_validate(_task_yaml())
    assert spec.version == "1"
    assert spec.limits.timeout_s == 300
    assert spec.env.image == "python:3.12-slim"
    assert isinstance(spec.grader, FileMatchGrader)


def test_task_id_pattern_is_enforced() -> None:
    with pytest.raises(Exception):
        TaskSpec.model_validate(_task_yaml(id="Bad_ID"))


def test_grader_union_discriminates_on_type() -> None:
    spec = TaskSpec.model_validate(
        _task_yaml(grader={"type": "script-exit", "script": "grader.sh"})
    )
    assert isinstance(spec.grader, ScriptExitGrader)

    spec = TaskSpec.model_validate(
        _task_yaml(
            grader={"type": "json-field", "path": "output/o.json", "field": "a.b", "expect": 1}
        )
    )
    assert isinstance(spec.grader, JsonFieldGrader)


def test_grader_path_traversal_is_rejected() -> None:
    with pytest.raises(Exception):
        FileMatchGrader(type="file-match", path="../escape.txt", expect="x")


def test_script_path_traversal_is_rejected() -> None:
    with pytest.raises(Exception):
        ScriptExitGrader(type="script-exit", script="../../grader.sh")


def test_task_json_payload_shape() -> None:
    spec = TaskSpec.model_validate(_task_yaml())
    payload = spec.task_json(["a.csv"])
    assert payload["task_id"] == "t001-hello"
    assert payload["input_files"] == ["a.csv"]
    assert payload["limits"]["timeout_s"] == 300


def test_agent_manifest_requires_image_or_build() -> None:
    with pytest.raises(Exception):
        AgentManifest(id="a", name="A")


def test_agent_manifest_build_requires_tag() -> None:
    with pytest.raises(Exception):
        AgentManifest(id="a", name="A", build=".")


def test_load_task_flags_missing_declared_file(tmp_path: Path) -> None:
    (tmp_path / "task.yaml").write_text(
        textwrap.dedent(
            """\
            id: t001-x
            name: X
            instruction: go
            files:
              - src: files/missing.csv
                dest: missing.csv
            grader:
              type: file-match
              path: output/report.txt
              expect: "1"
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(SpecError):
        load_task(tmp_path)


def test_load_task_reads_real_repo_task() -> None:
    repo = Path(__file__).resolve().parent.parent
    spec, tdir = load_task(repo / "evals" / "shell-mini" / "tasks" / "t001-hello")
    assert spec.id == "t001-hello"
