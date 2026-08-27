from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("FARADAY_RUNS_DIR", str(PROJECT_ROOT / "runs")))
EVALS_DIR = Path(os.environ.get("FARADAY_EVALS_DIR", str(PROJECT_ROOT / "evals")))
DATABASE_URL = os.environ.get(
    "FARADAY_DATABASE_URL",
    "postgresql+psycopg://faraday:faraday@127.0.0.1:15432/faraday",
)
REDIS_URL = os.environ.get("FARADAY_REDIS_URL", "redis://127.0.0.1:6379/0")
QUEUE_KEY = "faraday:jobs"
EVENTS_CHANNEL = "faraday:events"
API_HOST = os.environ.get("FARADAY_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("FARADAY_API_PORT", "8000"))
WEB_DIST = PROJECT_ROOT / "web" / "dist"


def _cors_origins() -> list[str]:
    raw = os.environ.get(
        "FARADAY_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


CORS_ORIGINS = _cors_origins()
# Allow uploaded (BYO) evals to ship script-exit / shell graders. Off by default:
# a public instance should not run arbitrary shell from strangers.
ALLOW_UPLOADED_SCRIPT_GRADERS = _flag("FARADAY_ALLOW_UPLOADED_SCRIPT_GRADERS")
