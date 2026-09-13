from __future__ import annotations

import json
import traceback
from pathlib import Path

from faraday.config import PROJECT_ROOT
from faraday.orchestrator.runner import LocalRunner
from faraday.queue import dequeue, publish_event
from faraday.store.db import Run, get_sessionmaker, utcnow


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
    run_id = job.get("run_id")
    if not run_id:
        print(f"[worker] dropping malformed job (no run_id): {job!r}")
        return

    SessionLocal = get_sessionmaker()
    try:
        task_dir = Path(job["task_dir"])
        agent_dir = Path(job["agent_dir"])

        with SessionLocal() as session:
            row = session.query(Run).filter_by(run_id=run_id).one_or_none()
            if row is None:
                return
            row.status = "running"
            row.started_at = row.started_at or utcnow()
            session.commit()

        runner = LocalRunner(PROJECT_ROOT)
        result, run_dir = runner.run(
            task_dir, agent_dir, run_id=run_id, env=job.get("env")
        )
        trajectory = _read_trajectory(run_dir)
        usage = result.usage or {}
        cost = None
        if usage:
            from faraday.pricing import estimate_cost_usd

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
        try:
            with SessionLocal() as session:
                row = session.query(Run).filter_by(run_id=run_id).one_or_none()
                if row is not None:
                    row.status = "error"
                    row.error = f"{type(e).__name__}: {e}"
                    row.finished_at = utcnow()
                    session.commit()
        except Exception:
            traceback.print_exc()
        try:
            publish_event({"type": "run.error", "run_id": run_id})
        except Exception:
            pass


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
        try:
            process_job(job)
        except Exception:
            traceback.print_exc()
            print(f"[worker] job {run_id} failed unexpectedly; continuing")
        print(f"[worker] finished run {run_id}")


if __name__ == "__main__":
    main()
