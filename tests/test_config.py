"""Tests for environment-driven config parsing."""

from __future__ import annotations

from bench import config


def test_cors_origins_default_is_the_dev_servers() -> None:
    assert config._cors_origins() == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_origins_split_and_trimmed(monkeypatch) -> None:
    monkeypatch.setenv("BENCH_CORS_ORIGINS", " https://a.example , https://b.example ")
    assert config._cors_origins() == ["https://a.example", "https://b.example"]


def test_cors_origins_wildcard(monkeypatch) -> None:
    monkeypatch.setenv("BENCH_CORS_ORIGINS", "*")
    assert config._cors_origins() == ["*"]
