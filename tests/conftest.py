"""Shared test configuration.

Point the platform at a throwaway SQLite database BEFORE any ``bench`` module is
imported, so API/DB tests never touch the real Postgres instance.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "bench-test.sqlite"
os.environ.setdefault("BENCH_DATABASE_URL", f"sqlite+pysqlite:///{_TMP_DB.as_posix()}")

import pytest  # noqa: E402


@pytest.fixture
def fresh_db():
    """Drop + recreate all tables around a test that needs a clean database."""
    from bench.store.db import Base, get_engine, get_sessionmaker

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield get_sessionmaker()
    Base.metadata.drop_all(engine)
