"""Tests for the cost estimation table."""

from __future__ import annotations

from faraday.pricing import estimate_cost_usd, resolve_price


def test_exact_model_match() -> None:
    price = resolve_price("gpt-4o")
    assert price == {"input": 2.50, "output": 10.00}


def test_prefix_match_falls_back_to_family() -> None:
    # dated / suffixed variants resolve to the family price
    assert resolve_price("gpt-4o-mini-2026-01-01") == resolve_price("gpt-4o-mini")


def test_case_and_whitespace_insensitive() -> None:
    assert resolve_price("  GPT-4O  ") == resolve_price("gpt-4o")


def test_unknown_model_has_no_price() -> None:
    assert resolve_price("who-knows-3") is None
    assert estimate_cost_usd("who-knows-3", 1000, 1000) is None


def test_empty_model_has_no_price() -> None:
    assert resolve_price("") is None
    assert resolve_price(None) is None  # type: ignore[arg-type]


def test_cost_is_tokens_times_rate() -> None:
    # 1M input @ $2.50 + 1M output @ $10.00
    assert estimate_cost_usd("gpt-4o", 1_000_000, 1_000_000) == 12.5


def test_zero_tokens_is_zero_cost() -> None:
    assert estimate_cost_usd("gpt-4o", 0, 0) == 0.0
