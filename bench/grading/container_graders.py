from __future__ import annotations

from pathlib import Path

from bench.grading.base import BaseGrader, GraderContext, GraderOutcome
from bench.spec import ScriptExitGrader

CONTAINER_GRADERS: dict[str, type[BaseGrader]] = {}


def register(cls):
    CONTAINER_GRADERS[cls.spec_type] = cls
    return cls


@register
class ScriptExitGrader_(BaseGrader):
    spec_type = "script-exit"

    def __init__(self, spec) -> None:
        super().__init__(spec)

    def grade(self, ctx: GraderContext) -> GraderOutcome:
        assert isinstance(self.spec, ScriptExitGrader)
        script_src = (ctx.task_dir / self.spec.script).resolve()
        if not script_src.is_file():
            return GraderOutcome(0.0, False, f"grader script missing: {self.spec.script}")

        if ctx.task_container is None:
            return GraderOutcome(
                0.0, False, "script-exit grader needs a live task-env container; none available"
            )

        host_dir = ctx.workspace / ".bench-grader"
        host_dir.mkdir(parents=True, exist_ok=True)
        host_script = host_dir / Path(self.spec.script).name
        host_script.write_bytes(script_src.read_bytes())

        container_path = f"/task/.bench-grader/{host_script.name}"
        result = ctx.task_container.exec_run(
            ["timeout", str(ctx.timeout_s), "bash", container_path],
            workdir="/task",
            demux=True,
        )
        stdout = (result.output[0] or b"").decode(errors="replace")
        stderr = (result.output[1] or b"").decode(errors="replace")
        tail = (stdout + stderr).strip()[-500:]

        if result.exit_code is None:
            return GraderOutcome(0.0, False, f"script produced no exit code; output: {tail}")
        if result.exit_code == 124:
            return GraderOutcome(0.0, False, f"grader script timed out after {ctx.timeout_s}s")
        ok = result.exit_code == 0
        detail = f"grader script exit={result.exit_code}"
        if tail:
            detail += f"; output:\n{tail}"
        return GraderOutcome(1.0 if ok else 0.0, ok, detail)
