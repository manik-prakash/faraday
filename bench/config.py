from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("BENCH_RUNS_DIR", str(PROJECT_ROOT / "runs")))
EVALS_DIR = Path(os.environ.get("BENCH_EVALS_DIR", str(PROJECT_ROOT / "evals")))
DATABASE_URL = os.environ.get(
    "BENCH_DATABASE_URL",
    "postgresql+psycopg://bench:bench@127.0.0.1:15432/bench",
)
REDIS_URL = os.environ.get("BENCH_REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_KEY = "bench:jobs"
EVENTS_CHANNEL = "bench:events"
API_HOST = os.environ.get("BENCH_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("BENCH_API_PORT", "8000"))
WEB_DIST = PROJECT_ROOT / "web" / "dist"


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "BENCH_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


CORS_ORIGINS = _cors_origins()
# Allow uploaded (BYO) evals to ship script-exit / shell graders. Off by default:
# a public instance should not run arbitrary shell from strangers.
ALLOW_UPLOADED_SCRIPT_GRADERS = _flag("BENCH_ALLOW_UPLOADED_SCRIPT_GRADERS")
