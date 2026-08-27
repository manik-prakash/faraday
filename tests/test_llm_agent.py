"""Tests for agents/llm-agent — a real BYO-key agent (HTTP mocked)."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import load_agent_solver

solve = load_agent_solver("llm-agent")


def test_solve_writes_answer_and_usage(tmp_path: Path) -> None:
    (tmp_path / "output").mkdir()

    def fake_call(_prompt: str):
        return "Canberra", {"model": "gpt-4o-mini", "input_tokens": 42, "output_tokens": 3}

    events = solve.solve(tmp_path, "What is the capital of Australia?", fake_call)

    assert (tmp_path / "output" / "answer.txt").read_text(encoding="utf-8").strip() == "Canberra"
    usage = json.loads((tmp_path / "output" / "usage.json").read_text(encoding="utf-8"))
    assert usage == {"model": "gpt-4o-mini", "input_tokens": 42, "output_tokens": 3}
    actions = [e["action"] for e in events]
    assert "llm_request" in actions and "llm_response" in actions


def test_solve_trims_and_strips_wrapping(tmp_path: Path) -> None:
    (tmp_path / "output").mkdir()

    def fake_call(_prompt: str):
        return '  "Jupiter"\n', {"model": "m", "input_tokens": 1, "output_tokens": 1}

    solve.solve(tmp_path, "Largest planet?", fake_call)
    assert (tmp_path / "output" / "answer.txt").read_text(encoding="utf-8").strip() == "Jupiter"


def test_openai_request_shape() -> None:
    url, headers, body = solve.openai_request("gpt-4o-mini", "sk-abc", "hi")
    assert url == "https://api.openai.com/v1/chat/completions"
    assert headers["Authorization"] == "Bearer sk-abc"
    payload = json.loads(body)
    assert payload["model"] == "gpt-4o-mini"
    assert payload["messages"][-1]["content"] == "hi"


def test_openai_response_parsing() -> None:
    raw = {
        "choices": [{"message": {"content": "  289  "}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        "model": "gpt-4o-mini-2026",
    }
    text, usage = solve.parse_openai_response(raw)
    assert text == "  289  "
    assert usage == {"model": "gpt-4o-mini-2026", "input_tokens": 10, "output_tokens": 2}


def test_anthropic_request_shape() -> None:
    url, headers, body = solve.anthropic_request("claude-haiku-4", "sk-ant", "hi")
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["x-api-key"] == "sk-ant"
    assert headers["anthropic-version"]
    payload = json.loads(body)
    assert payload["model"] == "claude-haiku-4"


def test_anthropic_response_parsing() -> None:
    raw = {
        "content": [{"type": "text", "text": "Nile"}],
        "usage": {"input_tokens": 8, "output_tokens": 1},
        "model": "claude-haiku-4",
    }
    text, usage = solve.parse_anthropic_response(raw)
    assert text == "Nile"
    assert usage == {"model": "claude-haiku-4", "input_tokens": 8, "output_tokens": 1}
