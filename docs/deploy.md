# Running & sharing

## One command (local, full stack)

```powershell
docker compose up -d --build     # postgres + redis + api/UI on :8000
bench worker                     # run the worker on the HOST (see note)
```

Open http://localhost:8000. Seed a populated leaderboard:

```powershell
./scripts/seed.ps1               # submits scripted-agent + dummy-agent across every eval
```

**Why the worker runs on the host:** it launches sibling Docker containers (task-env
+ agent) and bind-mounts a per-run staging directory into them. A worker running
*inside* a container would hand the host daemon paths only it can see. Keeping the
worker native side-steps that. The API, which only needs Postgres + Redis, runs
fine in `docker compose`.

## Share it (no hosting)

Expose the local API through a tunnel:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Set `BENCH_CORS_ORIGINS` to the tunnel origin (or `*` for a throwaway demo) so the
browser UI can call the API:

```powershell
$env:BENCH_CORS_ORIGINS = "*"; bench serve        # or set it in docker-compose.yml
```

## Config

| Env var | Default | Purpose |
|---|---|---|
| `BENCH_DATABASE_URL` | `postgresql+psycopg://bench:bench@127.0.0.1:15432/bench` | Postgres DSN |
| `BENCH_REDIS_URL` | `redis://127.0.0.1:6379/0` | queue + events |
| `BENCH_API_HOST` | `127.0.0.1` | bind address for `bench serve` |
| `BENCH_CORS_ORIGINS` | dev servers | comma-separated allowed origins, or `*` |
| `BENCH_EVALS_DIR` | `./evals` | where BYO evals are installed |
| `BENCH_RUNS_DIR` | `./runs` | run artifacts |
