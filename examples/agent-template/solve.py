"""Agent template — copy this directory and make it yours.

The platform mounts the task workspace at /task and runs this on container start.
Replace the body of `work()` with your agent (call your model, use tools, whatever
— you have network access).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

TASK = Path("/task")


def record(action: str, **detail: object) -> None:
    """Append one trajectory event (shown in the run's trajectory viewer)."""
    line = json.dumps({"ts": round(time.time(), 3), "action": action, "detail": detail})
    with (TASK / "output" / "trajectory.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def work(instruction: str) -> str:
    """YOUR AGENT GOES HERE. Return the text to write to output/answer.txt.

    Model API keys you pass at submit time (`--env OPENAI_API_KEY=...`) arrive as
    environment variables in THIS container only:

        key = os.environ["OPENAI_API_KEY"]
    """
    _ = os.environ  # keys live here
    return "replace me"


def main() -> None:
    (TASK / "output").mkdir(parents=True, exist_ok=True)
    task = json.loads((TASK / "task.json").read_text(encoding="utf-8"))
    record("read_task", task_id=task["task_id"])

    answer = work(task["instruction"])

    (TASK / "output" / "answer.txt").write_text(answer + "\n", encoding="utf-8")
    record("write_output", chars=len(answer))

    # Optional — lets the platform price the run:
    # (TASK / "output" / "usage.json").write_text(
    #     json.dumps({"model": "gpt-4o-mini", "input_tokens": 0, "output_tokens": 0})
    # )


if __name__ == "__main__":
    main()
