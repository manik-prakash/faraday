"""process_job must never crash the worker loop on a bad job or a transient error."""

from __future__ import annotations

from faraday.orchestrator.worker import process_job
from faraday.store.db import Run


def test_process_job_ignores_a_job_with_no_run_id(fresh_db) -> None:
    process_job({})  # must not raise


def test_process_job_marks_the_run_errored_on_a_malformed_job(fresh_db) -> None:
    SessionLocal = fresh_db
    with SessionLocal() as session:
        session.add(Run(run_id="r1", task_slug="t", agent_slug="a"))
        session.commit()

    process_job({"run_id": "r1"})  # missing task_dir / agent_dir -- must not raise

    with SessionLocal() as session:
        row = session.query(Run).filter_by(run_id="r1").one()
        assert row.status == "error"
        assert "task_dir" in row.error
