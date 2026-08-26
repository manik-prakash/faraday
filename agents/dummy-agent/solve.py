from __future__ import annotations

import csv
import glob
import json
import time
from pathlib import Path

TASK = Path("/task")


def record(action: str, detail: dict) -> None:
    entry = {"ts": round(time.time(), 3), "action": action, "detail": detail}
    with open(TASK / "output" / "trajectory.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def main() -> None:
    (TASK / "output").mkdir(parents=True, exist_ok=True)
    meta = json.loads((TASK / "task.json").read_text(encoding="utf-8"))
    record("read_task", {"task_id": meta["task_id"]})

    candidates = sorted(glob.glob(str(TASK / "input" / "*.csv")))
    if not candidates:
        record("error", {"message": "no csv found in /task/input"})
        raise SystemExit(1)

    total = 0
    rows = 0
    with open(candidates[0], newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            total += int(row.get("quantity", 0))
            rows += 1
    record("computed_total", {"source": Path(candidates[0]).name, "rows": rows, "total": total})

    (TASK / "output" / "report.txt").write_text(f"{total}\n", encoding="utf-8")
    record("wrote_report", {"path": "output/report.txt"})


if __name__ == "__main__":
    main()
