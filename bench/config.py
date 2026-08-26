from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("BENCH_RUNS_DIR", str(PROJECT_ROOT / "runs")))
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
