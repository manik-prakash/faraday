from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import case, func

from bench.config import CORS_ORIGINS, EVALS_DIR, RUNS_DIR, WEB_DIST
from bench.env_policy import EnvPolicyError, sanitize_agent_env
from bench.evals_io import install_eval_archive, sync_task_registry
from bench.exceptions import SpecError
from bench.queue import enqueue
from bench.spec import load_agent, load_task
from bench.store.artifacts import make_run_id
from bench.store.db import Agent, Run, Task, get_sessionmaker, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if EVALS_DIR.is_dir():
        SessionLocal = get_sessionmaker()
        with SessionLocal() as session:
            sync_task_registry(session, EVALS_DIR)
            session.commit()
    yield


app = FastAPI(title="bench", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SubmitRequest(BaseModel):
    task: str
    agent: str
    env: dict[str, str] | None = None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _run_dict(row: Run) -> dict:
    return {
        "run_id": row.run_id,
        "task_slug": row.task_slug,
        "agent_slug": row.agent_slug,
        "status": row.status,
        "score": row.score,
        "passed": row.passed,
        "duration_s": row.duration_s,
        "detail": row.detail,
        "error": row.error,
        "meta": row.meta,
        "model": row.model,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cost_usd": row.cost_usd,
        "queued_at": _iso(row.queued_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
    }


def _bench_name(task_dir: Path) -> str:
    p = task_dir.resolve()
    if p.parent.name == "tasks":
        return p.parent.parent.name
    return ""


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/runs")
def submit(req: SubmitRequest) -> dict:
    task_dir = Path(req.task).expanduser().resolve()
    agent_dir = Path(req.agent).expanduser().resolve()
    try:
        spec, _ = load_task(task_dir)
        manifest, _ = load_agent(agent_dir)
    except SpecError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    try:
        agent_env = sanitize_agent_env(req.env)
    except EnvPolicyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    SessionLocal = get_sessionmaker()
    run_id = make_run_id()
    with SessionLocal() as session:
        task_row = session.query(Task).filter_by(slug=spec.id).one_or_none()
        if task_row is None:
            task_row = Task(
                slug=spec.id,
                name=spec.name,
                description=spec.description,
                bench_name=_bench_name(task_dir),
                version=spec.version,
                instruction=spec.instruction,
                grader=spec.grader.model_dump(),
                limits=spec.limits.model_dump(),
            )
            session.add(task_row)
        agent_row = session.query(Agent).filter_by(slug=manifest.id).one_or_none()
        if agent_row is None:
            agent_row = Agent(
                slug=manifest.id, name=manifest.name, version=manifest.version
            )
            session.add(agent_row)
        session.add(Run(run_id=run_id, task_slug=spec.id, agent_slug=manifest.id))
        session.commit()

    job = {
        "run_id": run_id,
        "task_dir": str(task_dir),
        "agent_dir": str(agent_dir),
    }
    if agent_env:
        job["env"] = agent_env
    enqueue(job)
    return {"run_id": run_id, "status": "queued"}


@app.get("/api/runs")
def list_runs(limit: int = 50) -> dict:
    limit = max(1, min(limit, 200))
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        rows = session.query(Run).order_by(Run.queued_at.desc()).limit(limit).all()
    return {"runs": [_run_dict(r) for r in rows]}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        row = session.query(Run).filter_by(run_id=run_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    data = _run_dict(row)
    data["trajectory"] = row.trajectory or []
    run_dir = RUNS_DIR / run_id
    data["artifacts"] = {
        "run_dir": str(run_dir),
        "has_logs": (run_dir / "logs" / "agent.log").is_file(),
        "has_trajectory": bool(row.trajectory),
        "output_files": sorted(
            p.name for p in (run_dir / "output").glob("*") if p.is_file()
        )
        if (run_dir / "output").is_dir()
        else [],
    }
    return data


@app.get("/api/runs/{run_id}/logs")
def get_run_logs(run_id: str) -> FileResponse:
    log_path = RUNS_DIR / run_id / "logs" / "agent.log"
    if not log_path.is_file():
        raise HTTPException(status_code=404, detail="no agent log for this run")
    return FileResponse(log_path, media_type="text/plain")


@app.get("/api/tasks")
def list_tasks() -> dict:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        rows = session.query(Task).order_by(Task.slug).all()
    return {
        "tasks": [
            {
                "slug": t.slug,
                "name": t.name,
                "bench_name": t.bench_name,
                "description": t.description,
                "limits": t.limits,
            }
            for t in rows
        ]
    }


@app.get("/api/agents")
def list_agents() -> dict:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        rows = session.query(Agent).order_by(Agent.slug).all()
    return {
        "agents": [
            {"slug": a.slug, "name": a.name, "version": a.version} for a in rows
        ]
    }


@app.get("/api/leaderboard")
def leaderboard(task: str | None = None) -> dict:
    SessionLocal = get_sessionmaker()
    query_filters = []
    if task:
        query_filters.append(Run.task_slug == task)
    with SessionLocal() as session:
        base = (
            session.query(
                Run.task_slug.label("task_slug"),
                Run.agent_slug.label("agent_slug"),
                func.max(Run.score).label("best_score"),
                func.count(Run.id).label("runs"),
                func.sum(case((Run.passed.is_(True), 1), else_=0)).label("passes"),
                func.avg(Run.duration_s).label("avg_duration"),
                func.avg(Run.cost_usd).label("avg_cost"),
                func.max(Run.finished_at).label("last_run"),
            )
            .filter(*query_filters)
            .group_by(Run.task_slug, Run.agent_slug)
            .order_by(func.max(Run.score).desc())
        )
        rows = base.all()
    return {
        "leaderboard": [
            {
                "task_slug": r.task_slug,
                "agent_slug": r.agent_slug,
                "best_score": round(float(r.best_score or 0.0), 4),
                "runs": int(r.runs),
                "passes": int(r.passes or 0),
                "avg_duration_s": round(float(r.avg_duration), 3)
                if r.avg_duration is not None
                else None,
                "avg_cost_usd": round(float(r.avg_cost), 6)
                if r.avg_cost is not None
                else None,
                "last_run": _iso(r.last_run),
            }
            for r in rows
        ]
    }


@app.get("/api/evals")
def list_evals() -> dict:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        rows = (
            session.query(Task.bench_name, func.count(Task.id))
            .group_by(Task.bench_name)
            .order_by(Task.bench_name)
            .all()
        )
    return {
        "evals": [
            {"name": name or "(unfiled)", "tasks": int(count)} for name, count in rows
        ]
    }


@app.post("/api/evals")
async def upload_eval(name: str, request: Request) -> dict:
    data = await request.body()
    try:
        ids = install_eval_archive(data, name, EVALS_DIR)
    except SpecError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    SessionLocal = get_sessionmaker()
    with SessionLocal() as session:
        sync_task_registry(session, EVALS_DIR)
        session.commit()
    return {"name": name, "tasks": ids}


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
