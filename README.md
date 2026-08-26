# bench — bring-your-own-agent benchmark platform

A self-hostable platform where anyone ships their AI agent as a Docker image, runs it
against curated benchmarks (or brings their own evals), and gets scores, cost, and full
trajectories on a live leaderboard.

## Status

Phase 0 + 1 working: local run loop, Redis queue, worker pool, Postgres persistence,
FastAPI server, web leaderboard + trajectory viewer.

## Architecture

```
CLI ──► POST /api/runs ──► Redis queue ──► worker(s) ──► Docker Desktop
                                                             ├─ task-env container (no network)
                                                             ├─ agent container (untrusted, limited)
                                                             └─ grader (host-side, deterministic)
        Postgres ◄── results/trajectory/meta ◄──┘
             ▲
   FastAPI ──┴──► web UI (leaderboard, run detail, logs)
```

## Quickstart

Requires Docker Desktop running.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .

docker compose up -d          # postgres (:15432) + redis (:6379)
bench db-init

# terminal 1
bench serve                   # API on http://127.0.0.1:8000 (serves web/dist when built)

# terminal 2
bench worker                  # consumes the run queue

# submit a run
bench submit --task evals/shell-mini/tasks/t001-hello --agent agents/dummy-agent
```

Local-only mode (no infra needed): `bench run local --task ... --agent ...`

## Web UI

```powershell
cd web
npm install
npm run build                 # production build → served by `bench serve` at /
npm run dev                   # dev server on :5173 with /api proxied to :8000
```

Pages:
- **Leaderboard** (`/#/`) — best score per agent per task, score bars, recent runs table (live polling)
- **Run detail** (`/#/runs/<id>`) — status/score/meta, step-through **trajectory timeline**, agent log viewer

Note: this machine already had native/other Postgres instances on 5432–5434, so the
compose file maps ours to host port **15432** (override with `BENCH_DATABASE_URL`).

## Contracts

- **Task contract** — `docs/task-spec.md`
- **Agent contract** — `docs/agent-contract.md`
- Reference agent: `agents/dummy-agent`

Artifacts land in `runs/<run-id>/`: `result.json`, `task.yaml`, `logs/agent.log`,
`output/` (incl. `trajectory.jsonl`). Everything is also mirrored into Postgres.

## Roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Local run loop: task spec + agent container + grader | ✅ |
| 1 | Queue + workers, Postgres, API, leaderboard UI + trajectory viewer | ✅ |
| 2 | Ported benchmarks: shell-mini (~15 tasks), gaia-mini (~15 tasks), cost tracking | ⬜ |
| 3 | Original benchmark: DataWrangle-Bench | ⬜ |
| 4 | Deploy (VPS/tunnel), polish README/demo | ⬜ |

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | liveness |
| POST | `/api/runs` | submit `{task, agent}` (dirs) → queued run |
| GET | `/api/runs?limit=` | recent runs |
| GET | `/api/runs/{id}` | full detail incl. trajectory |
| GET | `/api/runs/{id}/logs` | raw agent log |
| GET | `/api/leaderboard?task=` | aggregated best scores |
| GET | `/api/tasks`, `/api/agents` | registries |
