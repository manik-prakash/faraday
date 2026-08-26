from __future__ import annotations

import re
from pathlib import Path

from bench.exceptions import BenchError
from bench.grading.base import BaseGrader, GraderOutcome
from bench.spec import FileMatchGrader, FileRegexGrader


def _read(workspace: Path, rel: str) -> str:
    path = (workspace / rel).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise BenchError(f"grader path escapes workspace: {rel}")
    if not path.is_file():
        raise BenchError(f"expected file not produced: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


def _score(ok: bool, detail_pass: str, detail_fail: str) -> GraderOutcome:
    return GraderOutcome(score=1.0 if ok else 0.0, passed=ok,
                         detail=detail_pass if ok else detail_fail)


class FileMatchGrader_(BaseGrader):
    def grade(self, workspace: Path) -> GraderOutcome:
        assert isinstance(self.spec, FileMatchGrader)
        text = _read(workspace, self.spec.path).strip()
        expect = self.spec.expect.strip()
        if self.spec.mode == "exact":
            ok = text == expect
            detail = f"exact match vs {expect!r}"
        else:
            ok = expect in text
            detail = f"contains {expect!r}"
        return _score(ok, f"{detail}: PASS", f"{detail}: FAIL (got {text[:200]!r})")


class FileRegexGrader_(BaseGrader):
    def grade(self, workspace: Path) -> GraderOutcome:
        assert isinstance(self.spec, FileRegexGrader)
        text = _read(workspace, self.spec.path)
        match = re.search(self.spec.pattern, text, re.DOTALL)
        return _score(
            match is not None,
            f"pattern {self.spec.pattern!r} matched",
            f"pattern {self.spec.pattern!r} did not match",
        )


GRADERS: dict[str, type[BaseGrader]] = {
    "file-match": FileMatchGrader_,
    "file-regex": FileRegexGrader_,
}


def run_grader(spec, workspace: Path) -> GraderOutcome:
    grader_cls = GRADERS.get(spec.type)
    if grader_cls is None:
        raise BenchError(f"unknown grader type: {spec.type}")
    try:
        return grader_cls(spec).grade(workspace)
    except BenchError as e:
        return GraderOutcome(score=0.0, passed=False, detail=str(e))
