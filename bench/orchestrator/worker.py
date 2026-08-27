from __future__ import annotations

import json
import traceback
from pathlib import Path

from bench.config import PROJECT_ROOT
from bench.orchestrator.runner import LocalRunner
from bench.queue import dequeue, publish_event
from bench.store.db import Run, get_sessionmaker, utcnow


def _read_trajectory(run_dir: Path) -> list:
    path = run_dir / "output" / "trajectory.jsonl"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"raw": line})
    return entries


def process_job(job: dict) -> None:
    run_id: str = job["run_id"]
    task_dir = Path(job["task_dir"])
    agent_dir = Path(job["agent_dir"])
    SessionLocal = get_sessionmaker()

    with SessionLocal() as session:
        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
        if row is None:
            return
        row.status = "running"
        row.started_at = row.started_at or utcnow()
        session.commit()

    try:
        runner = LocalRunner(PROJECT_ROOT)
        result, run_dir = runner.run(
            task_dir, agent_dir, run_id=run_id, env=job.get("env")
        )
        trajectory = _read_trajectory(run_dir)
        usage = result.usage or {}
        cost = None
        if usage:
            from bench.pricing import estimate_cost_usd

            cost = estimate_cost_usd(
                usage["model"], usage["input_tokens"], usage["output_tokens"]
            )
        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one()
            row.status = result.status
            row.score = result.score
            row.passed = result.passed
            row.duration_s = result.duration_s
            row.detail = result.detail
            row.trajectory = trajectory
            row.meta = result.meta
            row.model = usage.get("model")
            row.input_tokens = usage.get("input_tokens")
            row.output_tokens = usage.get("output_tokens")
            row.cost_usd = cost
            row.finished_at = utcnow()
            session.commit()
        publish_event(
            {"type": "run.finished", "run_id": run_id, "status": result.status}
        )
    except Exception as e:
        traceback.print_exc()
        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one_or_none()
            if row is not None:
                row.status = "error"
                row.error = f"{type(e).__name__}: {e}"
                row.finished_at = utcnow()
                session.commit()
        publish_event({"type": "run.error", "run_id": run_id})


def main(poll_timeout_s: int = 5) -> None:
    print(f"[worker] consuming queue (project={PROJECT_ROOT})")
    while True:
        try:
            job = dequeue(timeout_s=poll_timeout_s)
        except KeyboardInterrupt:
            print("[worker] shutting down")
            return
        except Exception as e:
            print(f"[worker] queue error: {e}")
            continue
        if job is None:
            continue
        run_id = job.get("run_id", "?")
        print(f"[worker] picked up run {run_id}")
        process_job(job)
        print(f"[worker] finished run {run_id}")


if __name__ == "__main__":
    main()
