"""Tests for LocalRunner._read_usage — the usage.json cost-tracking contract."""

from __future__ import annotations

import json
from pathlib import Path

from faraday.orchestrator.runner import _read_usage


def _write_usage(workspace: Path, payload: str) -> None:
    out = workspace / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "usage.json").write_text(payload, encoding="utf-8")


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert _read_usage(tmp_path) is None


def test_well_formed_usage_is_parsed(tmp_path: Path) -> None:
    _write_usage(
        tmp_path,
        json.dumps({"model": "gpt-4o", "input_tokens": 120, "output_tokens": 40}),
    )
    assert _read_usage(tmp_path) == {
        "model": "gpt-4o",
        "input_tokens": 120,
        "output_tokens": 40,
    }


def test_invalid_json_returns_none(tmp_path: Path) -> None:
    _write_usage(tmp_path, "{not json")
    assert _read_usage(tmp_path) is None


def test_non_object_json_returns_none(tmp_path: Path) -> None:
    # A JSON array (or string/number) is valid JSON but not a usage object.
    _write_usage(tmp_path, "[1, 2, 3]")
    assert _read_usage(tmp_path) is None


def test_negative_token_counts_rejected(tmp_path: Path) -> None:
    _write_usage(
        tmp_path,
        json.dumps({"model": "gpt-4o", "input_tokens": -5, "output_tokens": 10}),
    )
    assert _read_usage(tmp_path) is None


def test_boolean_token_counts_rejected(tmp_path: Path) -> None:
    # bool is a subclass of int; a usage payload with `true` is malformed.
    _write_usage(
        tmp_path,
        json.dumps({"model": "gpt-4o", "input_tokens": True, "output_tokens": 10}),
    )
    assert _read_usage(tmp_path) is None


def test_missing_model_returns_none(tmp_path: Path) -> None:
    _write_usage(tmp_path, json.dumps({"input_tokens": 1, "output_tokens": 2}))
    assert _read_usage(tmp_path) is None
