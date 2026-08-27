from __future__ import annotations

import json
import re

from faraday.exceptions import FaradayError
from faraday.grading.base import BaseGrader, GraderContext, GraderOutcome
from faraday.spec import FileMatchGrader, FileRegexGrader, JsonFieldGrader


def _read(ctx: GraderContext, rel: str) -> str:
    path = (ctx.workspace / rel).resolve()
    if not path.is_relative_to(ctx.workspace.resolve()):
        raise FaradayError(f"grader path escapes workspace: {rel}")
    if not path.is_file():
        raise FaradayError(f"expected file not produced: {rel}")
    return path.read_text(encoding="utf-8", errors="replace")


def _score(ok: bool, detail_pass: str, detail_fail: str) -> GraderOutcome:
    return GraderOutcome(
        score=1.0 if ok else 0.0,
        passed=ok,
        detail=detail_pass if ok else detail_fail,
    )


def _truncate(value: str, limit: int = 200) -> str:
    return value if len(value) <= limit else value[:limit] + "…"


class FileMatchGrader_(BaseGrader):
    def grade(self, ctx: GraderContext) -> GraderOutcome:
        assert isinstance(self.spec, FileMatchGrader)
        text = _read(ctx, self.spec.path)
        expect = self.spec.expect
        got = text.strip()
        want = expect.strip()
        if self.spec.ignore_case:
            got_cmp, want_cmp = got.lower(), want.lower()
        else:
            got_cmp, want_cmp = got, want
        if self.spec.mode == "exact":
            ok = got_cmp == want_cmp
            detail = f"exact match vs {expect!r}"
        else:
            ok = want_cmp in got_cmp
            detail = f"contains {expect!r}"
        return _score(ok, f"{detail}: PASS", f"{detail}: FAIL (got {_truncate(got)!r})")


class FileRegexGrader_(BaseGrader):
    def grade(self, ctx: GraderContext) -> GraderOutcome:
        assert isinstance(self.spec, FileRegexGrader)
        text = _read(ctx, self.spec.path)
        match = re.search(self.spec.pattern, text, re.DOTALL)
        return _score(
            match is not None,
            f"pattern {self.spec.pattern!r} matched",
            f"pattern {self.spec.pattern!r} did not match",
        )


class JsonFieldGrader_(BaseGrader):
    def grade(self, ctx: GraderContext) -> GraderOutcome:
        assert isinstance(self.spec, JsonFieldGrader)
        text = _read(ctx, self.spec.path)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return _score(False, "", f"invalid JSON in {self.spec.path}: {e}")
        current: object = data
        for part in self.spec.field.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return _score(
                    False,
                    "",
                    f"field {self.spec.field!r} missing (path broke at {part!r})",
                )
        expected: object = self.spec.expect
        if isinstance(expected, str) and isinstance(current, str):
            ok = current.strip() == expected.strip()
        else:
            ok = current == expected
        return _score(
            ok,
            f"{self.spec.field} == {expected!r}: PASS",
            f"{self.spec.field} == {expected!r}: FAIL (got {_truncate(str(current))!r})",
        )


GRADERS: dict[str, type[BaseGrader]] = {
    "file-match": FileMatchGrader_,
    "file-regex": FileRegexGrader_,
    "json-field": JsonFieldGrader_,
}


def run_grader(spec, ctx: GraderContext) -> GraderOutcome:
    from faraday.grading.container_graders import CONTAINER_GRADERS

    registry = {**GRADERS, **CONTAINER_GRADERS}
    grader_cls = registry.get(spec.type)
    if grader_cls is None:
        raise FaradayError(f"unknown grader type: {spec.type}")
    try:
        return grader_cls(spec).grade(ctx)
    except FaradayError as e:
        return GraderOutcome(score=0.0, passed=False, detail=str(e))
