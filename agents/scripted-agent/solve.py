"""Keyless scripted reference agent.

Solves every ``shell-mini`` task with a real, deterministic transform and answers
``gaia-mini`` from a small built-in table (two of them are genuinely computed).
It uses no network and no model API key — its purpose is to seed the leaderboard
with a meaningful non-zero baseline and to give the trajectory viewer real data.

The core is :func:`solve`, which operates on a workspace directory containing
``input/`` and ``output/`` so it can be unit-tested without Docker. ``__main__``
wires it to the platform's ``/task`` mount and writes ``trajectory.jsonl``.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

# --- shell-mini solvers ------------------------------------------------------


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _t001_hello(ws: Path) -> None:
    rows = _lines(ws / "input" / "quantities.csv")
    header = rows[0].split(",")
    qi = header.index("quantity")
    total = sum(int(r.split(",")[qi]) for r in rows[1:] if r.strip())
    (ws / "output" / "report.txt").write_text(f"{total}\n", encoding="utf-8")


def _t002_error_hunt(ws: Path) -> None:
    count = sum(
        1 for line in _lines(ws / "input" / "app_events.txt") if line.split()[:1] == ["ERROR"]
    )
    (ws / "output" / "report.txt").write_text(f"{count}\n", encoding="utf-8")


def _t003_dedupe(ws: Path) -> None:
    seen: list[str] = []
    for line in _lines(ws / "input" / "names.txt"):
        name = line.strip()
        if name and name not in seen:
            seen.append(name)
    (ws / "output" / "unique.txt").write_text("\n".join(seen) + "\n", encoding="utf-8")


def _t004_csv_filter(ws: Path) -> None:
    rows = [r for r in _lines(ws / "input" / "sales.csv") if r.strip()]
    header, body = rows[0], rows[1:]
    kept = [r for r in body if int(r.split(",")[-1]) > 100]
    (ws / "output" / "big_sales.csv").write_text(
        "\n".join([header, *kept]) + "\n", encoding="utf-8"
    )


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _t005_json_merge(ws: Path) -> None:
    a = json.loads((ws / "input" / "a.json").read_text(encoding="utf-8"))
    b = json.loads((ws / "input" / "b.json").read_text(encoding="utf-8"))
    merged = _deep_merge(a, b)
    (ws / "output" / "merged.json").write_text(json.dumps(merged, indent=2), encoding="utf-8")


def _t006_log_parse(ws: Path) -> None:
    errors = [
        line
        for line in _lines(ws / "input" / "server.log")
        if line.split(" ", 1)[0] == "ERROR"
    ]
    (ws / "output" / "errors.txt").write_text("\n".join(errors) + "\n", encoding="utf-8")


def _t007_rename_batch(ws: Path) -> None:
    dst = ws / "output" / "restored"
    dst.mkdir(parents=True, exist_ok=True)
    for src in sorted((ws / "input" / "backup").glob("*.txt.bak")):
        (dst / src.name[: -len(".bak")]).write_bytes(src.read_bytes())


def _t008_scaffold(ws: Path) -> None:
    for rel in (
        "project/src/main.py",
        "project/tests/test_main.py",
        "project/docs/index.md",
        "project/data/raw/.keep",
        "project/data/processed/.keep",
    ):
        p = ws / "output" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")


def _t009_env_to_json(ws: Path) -> None:
    obj: dict[str, str] = {}
    for line in _lines(ws / "input" / "config.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        obj[key.strip()] = value.strip()
    (ws / "output" / "config.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _t010_placeholder_purge(ws: Path) -> None:
    dst = ws / "output" / "site"
    dst.mkdir(parents=True, exist_ok=True)
    for src in sorted((ws / "input" / "pages").glob("*.html")):
        text = src.read_text(encoding="utf-8").replace("{{NAME}}", "Benchworm")
        (dst / src.name).write_text(text, encoding="utf-8")


def _t011_longest_line(ws: Path) -> None:
    best = ""
    for line in _lines(ws / "input" / "passage.txt"):
        stripped = line.strip()
        if len(stripped) > len(best):
            best = stripped
    (ws / "output" / "longest.txt").write_text(best + "\n", encoding="utf-8")


def _t012_anagram_groups(ws: Path) -> None:
    groups: dict[str, list[str]] = {}
    for line in _lines(ws / "input" / "words.txt"):
        word = line.strip()
        if not word:
            continue
        key = "".join(sorted(word))
        groups.setdefault(key, []).append(word)
    ordered = {k: sorted(v) for k, v in groups.items()}
    (ws / "output" / "groups.json").write_text(json.dumps(ordered, indent=2), encoding="utf-8")


def _t013_ini_to_json(ws: Path) -> None:
    result: dict[str, dict[str, object]] = {}
    section: dict[str, object] | None = None
    for raw in _lines(ws / "input" / "settings.ini"):
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = result.setdefault(line[1:-1], {})
        elif "=" in line and section is not None:
            key, value = (part.strip() for part in line.split("=", 1))
            section[key] = int(value) if re.fullmatch(r"-?\d+", value) else value
    (ws / "output" / "settings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def _t014_fibonacci(ws: Path) -> None:
    seq = [0, 1]
    while len(seq) < 20:
        seq.append(seq[-1] + seq[-2])
    (ws / "output" / "fib.txt").write_text(" ".join(map(str, seq)), encoding="utf-8")


def _t015_link_extractor(ws: Path) -> None:
    md = (ws / "input" / "readme.md").read_text(encoding="utf-8")
    urls = re.findall(r"\[[^\]]*\]\(([^)]+)\)", md)
    (ws / "output" / "links.txt").write_text("\n".join(urls) + "\n", encoding="utf-8")


# --- datawrangle-mini solvers --------------------------------------------


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    rows = [line.split(",") for line in path.read_text(encoding="utf-8").splitlines() if line != ""]
    return rows[0], rows[1:]


def _write_csv(ws: Path, name: str, header: list[str], rows: list[list[str]]) -> None:
    lines = [",".join(header)] + [",".join(r) for r in rows]
    (ws / "output" / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dw_select_columns(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "people.csv")
    keep = [header.index("name"), header.index("city")]
    _write_csv(ws, "trimmed.csv", ["name", "city"], [[r[i] for i in keep] for r in rows])


def _dw_filter_rows(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "orders.csv")
    si = header.index("status")
    _write_csv(ws, "paid.csv", header, [r for r in rows if r[si] == "paid"])


def _dw_sort_by(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "scores.csv")
    ordered = sorted(rows, key=lambda r: (-int(r[1]), r[0]))
    _write_csv(ws, "ranked.csv", header, ordered)


def _dw_group_sum(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "sales.csv")
    totals: dict[str, int] = {}
    for region, amount in rows:
        totals[region] = totals.get(region, 0) + int(amount)
    out = [[k, str(totals[k])] for k in sorted(totals)]
    _write_csv(ws, "by_region.csv", ["region", "total"], out)


def _dw_dedupe_key(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "contacts.csv")
    seen: set[str] = set()
    kept = []
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0])
            kept.append(row)
    _write_csv(ws, "unique.csv", header, kept)


def _dw_join(ws: Path) -> None:
    _, users = _read_csv(ws / "input" / "users.csv")
    id_to_name = {uid: name for uid, name in users}
    _, orders = _read_csv(ws / "input" / "orders.csv")
    _write_csv(ws, "joined.csv", ["name", "item"], [[id_to_name[u], item] for u, item in orders])


def _dw_reshape_long(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "wide.csv")
    months = header[1:]
    out = [[row[0], month, row[i + 1]] for row in rows for i, month in enumerate(months)]
    _write_csv(ws, "long.csv", ["name", "month", "value"], out)


def _dw_fill_nulls(ws: Path) -> None:
    header, rows = _read_csv(ws / "input" / "readings.csv")
    filled = [[cell if cell != "" else "0" for cell in row] for row in rows]
    _write_csv(ws, "filled.csv", header, filled)


def _dw_json_to_csv(ws: Path) -> None:
    records = json.loads((ws / "input" / "records.json").read_text(encoding="utf-8"))
    out = [[str(rec["name"]), str(rec["age"])] for rec in records]
    _write_csv(ws, "records.csv", ["name", "age"], out)


def _dw_csv_to_json(ws: Path) -> None:
    _, rows = _read_csv(ws / "input" / "table.csv")
    obj = {key: value for key, value in rows}
    (ws / "output" / "table.json").write_text(json.dumps(obj, indent=2), encoding="utf-8")


DATAWRANGLE_SOLVERS = {
    "d001-select-columns": _dw_select_columns,
    "d002-filter-rows": _dw_filter_rows,
    "d003-sort-by": _dw_sort_by,
    "d004-group-sum": _dw_group_sum,
    "d005-dedupe-key": _dw_dedupe_key,
    "d006-join": _dw_join,
    "d007-reshape-long": _dw_reshape_long,
    "d008-fill-nulls": _dw_fill_nulls,
    "d009-json-to-csv": _dw_json_to_csv,
    "d010-csv-to-json": _dw_csv_to_json,
}


SHELL_SOLVERS = {
    "t001-hello": _t001_hello,
    "t002-error-hunt": _t002_error_hunt,
    "t003-dedupe": _t003_dedupe,
    "t004-csv-filter": _t004_csv_filter,
    "t005-json-merge": _t005_json_merge,
    "t006-log-parse": _t006_log_parse,
    "t007-rename-batch": _t007_rename_batch,
    "t008-scaffold": _t008_scaffold,
    "t009-env-to-json": _t009_env_to_json,
    "t010-placeholder-purge": _t010_placeholder_purge,
    "t011-longest-line": _t011_longest_line,
    "t012-anagram-groups": _t012_anagram_groups,
    "t013-ini-to-json": _t013_ini_to_json,
    "t014-fibonacci": _t014_fibonacci,
    "t015-link-extractor": _t015_link_extractor,
}

FILE_SOLVERS = {**SHELL_SOLVERS, **DATAWRANGLE_SOLVERS}

# --- gaia-mini answers -----------------------------------------------------
# Knowledge answers are a canned table (this is a reference/demo agent, not a
# leaderboard contender). g011 and g014 are genuinely computed below.

GAIA_ANSWERS = {
    "g001-periodic-count": "118",
    "g002-capital-australia": "Canberra",
    "g003-guitar-strings": "6",
    "g004-titanic-year": "1912",
    "g005-largest-planet": "Jupiter",
    "g006-gold-symbol": "Au",
    "g007-1984-author": "George Orwell",
    "g008-speed-of-light": "299792458",
    "g009-mona-lisa": "Leonardo da Vinci",
    "g010-river-egypt": "Nile",
    "g011-square-17": str(17**2),
    "g012-continents": "7",
    "g013-moon-walker": "Armstrong",
    "g014-binary-ten": format(10, "b"),
    "g015-japan-currency": "yen",
}


def solve(task_root: Path, task_id: str) -> list[dict]:
    """Run the solver for ``task_id`` against a workspace directory.

    ``task_root`` must contain ``input/`` (task files) and ``output/`` (where
    results are written). Returns a list of trajectory events. Raises
    ``KeyError`` if no solver is registered for ``task_id``.
    """
    task_root = Path(task_root)
    (task_root / "output").mkdir(parents=True, exist_ok=True)

    def event(action: str, **detail: object) -> dict:
        return {"ts": round(time.time(), 3), "action": action, "detail": detail}

    events = [event("read_task", task_id=task_id)]

    if task_id in FILE_SOLVERS:
        FILE_SOLVERS[task_id](task_root)
        events.append(event("solved", kind="file"))
    elif task_id in GAIA_ANSWERS:
        answer = GAIA_ANSWERS[task_id]
        (task_root / "output" / "answer.txt").write_text(answer + "\n", encoding="utf-8")
        events.append(event("answered", answer=answer))
    else:
        raise KeyError(f"no scripted solver for task {task_id!r}")

    events.append(event("write_output"))
    return events


def _append_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in events:
            fh.write(json.dumps(entry) + "\n")


def main() -> None:
    task = Path("/task")
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    task_id = meta["task_id"]
    trajectory = task / "output" / "trajectory.jsonl"
    try:
        events = solve(task, task_id)
    except KeyError as e:
        _append_events(trajectory, [{"ts": round(time.time(), 3), "action": "error",
                                     "detail": {"message": str(e)}}])
        raise SystemExit(1) from e
    _append_events(trajectory, events)


if __name__ == "__main__":
    main()
