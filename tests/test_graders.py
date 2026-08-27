"""Tests for the host-side deterministic graders."""

from __future__ import annotations

from pathlib import Path

import pytest

from bench.grading import run_grader
from bench.grading.base import GraderContext
from bench.spec import FileMatchGrader, FileRegexGrader, JsonFieldGrader


def _ctx(tmp_path: Path, files: dict[str, str]) -> GraderContext:
    ws = tmp_path / "workspace"
    (ws / "output").mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return GraderContext(workspace=ws, task_dir=tmp_path)


# ---- file-match ---------------------------------------------------------------

def test_file_match_exact_pass(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/report.txt": "142\n"})
    out = run_grader(FileMatchGrader(type="file-match", path="output/report.txt", expect="142"), ctx)
    assert out.passed and out.score == 1.0


def test_file_match_exact_fail_reports_got(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/report.txt": "999"})
    out = run_grader(FileMatchGrader(type="file-match", path="output/report.txt", expect="142"), ctx)
    assert not out.passed and out.score == 0.0
    assert "999" in out.detail


def test_file_match_contains_mode(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/a.txt": "the answer is 42 today"})
    out = run_grader(
        FileMatchGrader(type="file-match", path="output/a.txt", expect="42", mode="contains"), ctx
    )
    assert out.passed


def test_file_match_ignore_case(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/a.txt": "CANBERRA"})
    out = run_grader(
        FileMatchGrader(type="file-match", path="output/a.txt", expect="canberra", ignore_case=True),
        ctx,
    )
    assert out.passed


def test_file_match_missing_file_is_failure_not_crash(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {})
    out = run_grader(FileMatchGrader(type="file-match", path="output/nope.txt", expect="x"), ctx)
    assert not out.passed
    assert "not produced" in out.detail


# ---- file-regex -------------------------------------------------------------

def test_file_regex_dotall_match(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/r.json": '{\n  "status": "ok"\n}'})
    out = run_grader(
        FileRegexGrader(type="file-regex", path="output/r.json", pattern=r'"status":\s*"ok"'), ctx
    )
    assert out.passed


def test_file_regex_no_match_fails(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/r.txt": "nothing here"})
    out = run_grader(FileRegexGrader(type="file-regex", path="output/r.txt", pattern=r"ERROR"), ctx)
    assert not out.passed


# ---- json-field -----------------------------------------------------------

def test_json_field_nested_hit(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/o.json": '{"services": {"cache": {"ttl_seconds": 600}}}'})
    out = run_grader(
        JsonFieldGrader(
            type="json-field", path="output/o.json", field="services.cache.ttl_seconds", expect=600
        ),
        ctx,
    )
    assert out.passed


def test_json_field_missing_path_reports_break_point(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/o.json": '{"services": {}}'})
    out = run_grader(
        JsonFieldGrader(
            type="json-field", path="output/o.json", field="services.cache.ttl", expect=1
        ),
        ctx,
    )
    assert not out.passed
    assert "cache" in out.detail


def test_json_field_invalid_json_fails_cleanly(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/o.json": "{oops"})
    out = run_grader(
        JsonFieldGrader(type="json-field", path="output/o.json", field="a", expect=1), ctx
    )
    assert not out.passed
    assert "JSON" in out.detail


def test_json_field_string_compare_is_trimmed(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {"output/o.json": '{"name": "  alice  "}'})
    out = run_grader(
        JsonFieldGrader(type="json-field", path="output/o.json", field="name", expect="alice"), ctx
    )
    assert out.passed


# ---- run_grader dispatch --------------------------------------------------

def test_unknown_grader_type_raises(tmp_path: Path) -> None:
    class Fake:
        type = "does-not-exist"

    with pytest.raises(Exception):
        run_grader(Fake(), _ctx(tmp_path, {}))


def test_workspace_escape_is_blocked(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, {})
    grader = FileMatchGrader.model_construct(
        type="file-match", path="output/../../secret", expect="x", mode="exact", ignore_case=False
    )
    out = run_grader(grader, ctx)
    assert not out.passed
    assert "escape" in out.detail
