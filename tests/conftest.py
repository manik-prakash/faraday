"""Shared test configuration.

Point the platform at a throwaway SQLite database BEFORE any ``faraday`` module is
imported, so API/DB tests never touch the real Postgres instance.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_DB = Path(tempfile.gettempdir()) / "faraday-test.sqlite"
os.environ.setdefault("FARADAY_DATABASE_URL", f"sqlite+pysqlite:///{_TMP_DB.as_posix()}")

import importlib.util  # noqa: E402

import pytest  # noqa: E402


def load_agent_solver(agent_dir_name: str):
    """Import an agent's ``solve.py`` under a unique module name.

    Agents each ship a file literally called ``solve.py``; importing them as a
    bare ``solve`` module makes them collide in ``sys.modules``.
    """
    mod_name = f"_agent_solve_{agent_dir_name.replace('-', '_')}"
    path = Path(__file__).resolve().parent.parent / "agents" / agent_dir_name / "solve.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fresh_db():
    """Drop + recreate all tables around a test that needs a clean database."""
    from faraday.store.db import Base, get_engine, get_sessionmaker

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield get_sessionmaker()
    Base.metadata.drop_all(engine)
