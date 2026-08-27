"""Tests for the CLI's --env / --env-file collection helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from faraday.cli import _collect_env
from faraday.env_policy import EnvPolicyError


def test_inline_pairs_are_parsed() -> None:
    assert _collect_env(["OPENAI_API_KEY=sk-1", "FARADAY_MODEL=gpt-4o"], None) == {
        "OPENAI_API_KEY": "sk-1",
        "FARADAY_MODEL": "gpt-4o",
    }


def test_env_file_is_read_and_comments_skipped(tmp_path: Path) -> None:
    f = tmp_path / "keys.env"
    f.write_text("# creds\nANTHROPIC_API_KEY=sk-ant\n\nFARADAY_TAG=x=y\n", encoding="utf-8")
    assert _collect_env([], f) == {"ANTHROPIC_API_KEY": "sk-ant", "FARADAY_TAG": "x=y"}


def test_inline_pair_overrides_file(tmp_path: Path) -> None:
    f = tmp_path / "keys.env"
    f.write_text("OPENAI_API_KEY=from-file\n", encoding="utf-8")
    assert _collect_env(["OPENAI_API_KEY=from-cli"], f) == {"OPENAI_API_KEY": "from-cli"}


def test_disallowed_key_raises() -> None:
    with pytest.raises(EnvPolicyError):
        _collect_env(["PATH=/tmp"], None)


def test_malformed_pair_raises() -> None:
    with pytest.raises(ValueError):
        _collect_env(["NOEQUALS"], None)


def test_empty_returns_empty_dict() -> None:
    assert _collect_env([], None) == {}
