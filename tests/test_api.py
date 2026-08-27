"""API-surface tests using FastAPI's TestClient against a SQLite database."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parent.parent
DUMMY_AGENT = REPO / "agents" / "dummy-agent"
T001 = REPO / "evals" / "shell-mini" / "tasks" / "t001-hello"


@pytest.fixture
def client(fresh_db):
    from bench.api.main import app

    with TestClient(app) as c:
        yield c


def test_healthz(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_submit_rejects_unknown_task_path(client) -> None:
    r = client.post("/api/runs", json={"task": str(REPO / "nope"), "agent": str(DUMMY_AGENT)})
    assert r.status_code == 400


def test_submit_queues_run_and_persists_row(client, monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr("bench.api.main.enqueue", calls.append)

    r = client.post("/api/runs", json={"task": str(T001), "agent": str(DUMMY_AGENT)})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    run_id = body["run_id"]

    assert len(calls) == 1 and calls[0]["run_id"] == run_id

    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["run_id"] == run_id
    assert detail["task_slug"] == "t001-hello"
    assert detail["agent_slug"] == "dummy-agent"
    # Phase 2 cost fields are present on the payload, null before a worker runs.
    for key in ("model", "input_tokens", "output_tokens", "cost_usd"):
        assert key in detail and detail[key] is None


def test_get_unknown_run_is_404(client) -> None:
    assert client.get("/api/runs/does-not-exist").status_code == 404


def test_list_evals_reflects_registered_tasks(client) -> None:
    # lifespan sync registers the repo's curated evals on startup
    evals = {e["name"]: e["tasks"] for e in client.get("/api/evals").json()["evals"]}
    assert evals.get("shell-mini") == 15
    assert evals.get("gaia-mini") == 15
    assert evals.get("datawrangle-mini") == 10


def test_post_eval_archive_installs_and_registers(client, tmp_path, monkeypatch) -> None:
    import io
    import zipfile

    from bench.api import main as api_main

    monkeypatch.setattr(api_main, "EVALS_DIR", tmp_path / "evals")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "tasks/up001-demo/task.yaml",
            'id: up001-demo\nname: Demo\ninstruction: write it\n'
            'grader:\n  type: file-match\n  path: output/a.txt\n  expect: "ok"\n',
        )

    r = client.post("/api/evals?name=uploaded-demo", content=buf.getvalue())
    assert r.status_code == 200, r.text
    assert r.json()["tasks"] == ["up001-demo"]

    names = {e["name"] for e in client.get("/api/evals").json()["evals"]}
    assert "uploaded-demo" in names


def test_submit_with_allowed_env_queues_without_leaking_values(client, monkeypatch) -> None:
    jobs: list[dict] = []
    monkeypatch.setattr("bench.api.main.enqueue", jobs.append)

    r = client.post(
        "/api/runs",
        json={
            "task": str(T001),
            "agent": str(DUMMY_AGENT),
            "env": {"OPENAI_API_KEY": "sk-secret-value"},
        },
    )
    assert r.status_code == 200
    # the value travels on the local job payload for the worker...
    assert jobs[0]["env"] == {"OPENAI_API_KEY": "sk-secret-value"}
    # ...but the API response never echoes it back
    assert "sk-secret-value" not in r.text


def test_submit_with_disallowed_env_is_rejected(client, monkeypatch) -> None:
    monkeypatch.setattr("bench.api.main.enqueue", lambda job: None)
    r = client.post(
        "/api/runs",
        json={"task": str(T001), "agent": str(DUMMY_AGENT), "env": {"LD_PRELOAD": "/evil.so"}},
    )
    assert r.status_code == 400
    assert "LD_PRELOAD" in r.text


def test_leaderboard_takes_best_score_per_agent(client, fresh_db) -> None:
    from bench.store.db import Run

    SessionLocal = fresh_db
    with SessionLocal() as s:
        s.add_all(
            [
                Run(run_id="r1", task_slug="t", agent_slug="a", status="failed", score=0.0, passed=False),
                Run(run_id="r2", task_slug="t", agent_slug="a", status="passed", score=1.0, passed=True),
            ]
        )
        s.commit()

    board = client.get("/api/leaderboard").json()["leaderboard"]
    row = next(r for r in board if r["task_slug"] == "t" and r["agent_slug"] == "a")
    assert row["best_score"] == 1.0
    assert row["runs"] == 2
    assert row["passes"] == 1


def test_leaderboard_reports_average_cost(client, fresh_db) -> None:
    from bench.store.db import Run

    SessionLocal = fresh_db
    with SessionLocal() as s:
        s.add_all(
            [
                Run(run_id="c1", task_slug="t", agent_slug="a", score=1.0, passed=True, cost_usd=0.02),
                Run(run_id="c2", task_slug="t", agent_slug="a", score=1.0, passed=True, cost_usd=0.04),
                Run(run_id="c3", task_slug="t", agent_slug="b", score=0.0, passed=False),
            ]
        )
        s.commit()

    board = client.get("/api/leaderboard").json()["leaderboard"]
    row_a = next(r for r in board if r["agent_slug"] == "a")
    row_b = next(r for r in board if r["agent_slug"] == "b")
    assert row_a["avg_cost_usd"] == pytest.approx(0.03)
    assert row_b["avg_cost_usd"] is None  # keyless agent: no cost recorded
