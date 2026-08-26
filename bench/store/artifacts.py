from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field as dataclasses_field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RunResult:
    run_id: str
    task_id: str
    agent_id: str
    status: str
    score: float
    passed: bool
    duration_s: float
    detail: str
    started_at: str
    finished_at: str
    meta: dict = dataclasses_field(default_factory=dict)

    def save(self, run_dir: Path) -> Path:
        path = run_dir / "result.json"
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


class RunLayout:
    def __init__(self, project_root: Path, run_id: str) -> None:
        self.run_id = run_id
        self.run_dir = Path(project_root) / "runs" / run_id
        self.output_dir = self.run_dir / "output"
        self.logs_dir = self.run_dir / "logs"

    def create(self) -> "RunLayout":
        for d in (self.run_dir, self.output_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)
        return self

    @staticmethod
    def latest(project_root: Path) -> Path | None:
        runs = sorted((Path(project_root) / "runs").glob("*"))
        return runs[-1] if runs else None
