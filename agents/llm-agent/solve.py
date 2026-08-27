"""A minimal real BYO-key agent.

Reads the task instruction, makes ONE chat-completion call to OpenAI or Anthropic
(key supplied by the platform's BYO-key plumbing), writes the reply to
``output/answer.txt`` and token usage to ``output/usage.json``. Tuned for short
factual / computational tasks (gaia-mini style).

Env:
  OPENAI_API_KEY / ANTHROPIC_API_KEY   the key (one of; picked automatically)
  BENCH_LLM_PROVIDER   openai | anthropic   (default: whichever key is present)
  BENCH_LLM_MODEL      model id             (default: gpt-4o-mini / claude-haiku-4-5)

stdlib only — no pip install, image stays `python:3.12-slim`.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

_ANTHROPIC_VERSION = "2023-06-01"
_SYSTEM = (
    "You are solving a benchmark task. Reply with ONLY the exact answer that should "
    "be written to the output file - no explanation, no quotes, no code fences, no "
    "trailing punctuation unless it is part of the answer."
)


# --- request / response shaping (pure, unit-tested) -------------------------

def openai_request(model: str, key: str, prompt: str) -> tuple[str, dict, bytes]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
    ).encode()
    return url, headers, body


def parse_openai_response(raw: dict) -> tuple[str, dict]:
    text = raw["choices"][0]["message"]["content"]
    u = raw.get("usage", {})
    return text, {
        "model": raw.get("model", ""),
        "input_tokens": int(u.get("prompt_tokens", 0)),
        "output_tokens": int(u.get("completion_tokens", 0)),
    }


def anthropic_request(model: str, key: str, prompt: str) -> tuple[str, dict, bytes]:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": key,
        "anthropic-version": _ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 512,
            "system": _SYSTEM,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    return url, headers, body


def parse_anthropic_response(raw: dict) -> tuple[str, dict]:
    text = "".join(b.get("text", "") for b in raw.get("content", []) if b.get("type") == "text")
    u = raw.get("usage", {})
    return text, {
        "model": raw.get("model", ""),
        "input_tokens": int(u.get("input_tokens", 0)),
        "output_tokens": int(u.get("output_tokens", 0)),
    }


# --- solve core (call_llm injected, unit-tested) ---------------------------

def solve(task_root: Path, instruction: str, call_llm) -> list[dict]:
    """Answer ``instruction`` via ``call_llm(prompt) -> (text, usage_dict)``."""
    task_root = Path(task_root)
    (task_root / "output").mkdir(parents=True, exist_ok=True)
    events = [{"ts": round(time.time(), 3), "action": "read_task", "detail": {}}]

    def ev(action: str, **detail: object) -> dict:
        return {"ts": round(time.time(), 3), "action": action, "detail": detail}

    prompt = f"Task:\n{instruction}\n\nAnswer:"
    events.append(ev("llm_request", chars=len(prompt)))
    text, usage = call_llm(prompt)
    events.append({"ts": round(time.time(), 3), "action": "llm_response", "detail": usage})

    answer = text.strip().strip('"').strip()
    (task_root / "output" / "answer.txt").write_text(answer + "\n", encoding="utf-8")
    (task_root / "output" / "usage.json").write_text(json.dumps(usage), encoding="utf-8")
    events.append(ev("write_output", answer=answer))
    return events


# --- wiring --------------------------------------------------------------

def _http_json(url: str, headers: dict, body: bytes) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 - fixed API hosts
        return json.loads(resp.read())


def _make_call_llm():
    provider = os.environ.get("BENCH_LLM_PROVIDER", "").lower()
    if not provider:
        provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "openai"
    if provider == "anthropic":
        key = os.environ["ANTHROPIC_API_KEY"]
        model = os.environ.get("BENCH_LLM_MODEL", "claude-haiku-4-5")
        build, parse = anthropic_request, parse_anthropic_response
    else:
        key = os.environ["OPENAI_API_KEY"]
        model = os.environ.get("BENCH_LLM_MODEL", "gpt-4o-mini")
        build, parse = openai_request, parse_openai_response

    def call_llm(prompt: str) -> tuple[str, dict]:
        url, headers, body = build(model, key, prompt)
        return parse(_http_json(url, headers, body))

    return call_llm


def main() -> None:
    task = Path("/task")
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    traj = task / "output" / "trajectory.jsonl"
    traj.parent.mkdir(parents=True, exist_ok=True)
    try:
        events = solve(task, meta["instruction"], _make_call_llm())
    except (KeyError, urllib.error.URLError, urllib.error.HTTPError) as e:
        with traj.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": round(time.time(), 3), "action": "error",
                                 "detail": {"message": f"{type(e).__name__}: {e}"}}) + "\n")
        raise SystemExit(1) from e
    with traj.open("a", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


if __name__ == "__main__":
    main()
