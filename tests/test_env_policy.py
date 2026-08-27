"""Tests for the agent-environment allowlist (BYO API keys)."""

from __future__ import annotations

import pytest

from bench.env_policy import EnvPolicyError, sanitize_agent_env


def test_api_key_suffix_is_allowed() -> None:
    env = {"OPENAI_API_KEY": "sk-x", "MISTRAL_API_KEY": "y"}
    assert sanitize_agent_env(env) == env


def test_known_provider_prefixes_are_allowed() -> None:
    env = {"ANTHROPIC_BASE_URL": "https://x", "BENCH_MODEL": "gpt-4o"}
    assert sanitize_agent_env(env) == env


def test_unrelated_keys_are_rejected() -> None:
    with pytest.raises(EnvPolicyError) as exc:
        sanitize_agent_env({"OPENAI_API_KEY": "ok", "LD_PRELOAD": "/evil.so"})
    assert "LD_PRELOAD" in str(exc.value)


def test_lowercase_names_are_rejected() -> None:
    with pytest.raises(EnvPolicyError):
        sanitize_agent_env({"openai_api_key": "sk-x"})


def test_none_and_empty_are_noops() -> None:
    assert sanitize_agent_env(None) == {}
    assert sanitize_agent_env({}) == {}


def test_non_string_values_are_rejected() -> None:
    with pytest.raises(EnvPolicyError):
        sanitize_agent_env({"OPENAI_API_KEY": 123})  # type: ignore[dict-item]
