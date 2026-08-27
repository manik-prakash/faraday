# bench — bring-your-own-agent benchmark platform

A self-hostable platform where anyone ships their AI agent as a Docker image, runs it
against curated benchmarks (or brings their own evals), and gets scores, cost, and full
trajectories on a live leaderboard.

## Status

Phases 0–3 working: local run loop, Redis queue, worker pool, Postgres persistence,
FastAPI server, web leaderboard + trajectory viewer, three ported/original eval sets
(40 tasks), per-run token/cost tracking, bring-your-own API keys, and bring-your-own
eval upload. ~110 unit tests + a Docker-marked end-to-end suite.

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
.venv\Scripts\pip install -e ".[dev]"

docker compose up -d --build   # postgres (:15432) + redis (:6379) + api/UI (:8000)
bench db-init                   # add --reset after a schema change

bench worker                    # terminal 2 — consumes the queue (runs on the host)

# submit runs; scripted-agent actually solves shell-mini + datawrangle-mini
bench submit --task evals/datawrangle-mini/tasks/d006-join --agent agents/scripted-agent
./scripts/seed.ps1              # or: populate the whole leaderboard at once
```

Local-only mode (no infra needed): `bench run local --task ... --agent ...`

Bring your own model keys: `--env OPENAI_API_KEY=sk-...` / `--env-file .env` on
`bench submit` and `bench run local` (see `docs/agent-contract.md`). Bring your own
eval: `bench eval add ./my-eval --name my-eval` (see `docs/byo-eval.md`).
Sharing & config: `docs/deploy.md`.

Run the tests: `pytest -m "not docker"` (add a daemon and drop the filter for the
end-to-end suite).

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
| 2 | Ported benchmarks: shell-mini (15), gaia-mini (15); `json-field` + `script-exit` graders; token/cost tracking | ✅ |
| 3 | Original benchmark: DataWrangle-Bench (10); BYO API keys; BYO-eval upload | ✅ |
| 4 | One-command stack, tunnel sharing, test suite + CI, README/demo | ✅ |

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz` | liveness |
| POST | `/api/runs` | submit `{task, agent, env?}` (dirs; `env` = BYO keys) → queued run |
| GET | `/api/runs?limit=` | recent runs |
| GET | `/api/runs/{id}` | full detail incl. trajectory |
| GET | `/api/runs/{id}/logs` | raw agent log |
| GET | `/api/leaderboard?task=` | aggregated best scores + avg cost |
| GET | `/api/tasks`, `/api/agents` | registries |
| GET | `/api/evals` | eval names + task counts |
| POST | `/api/evals?name=` | install a BYO-eval zip (raw body) |
