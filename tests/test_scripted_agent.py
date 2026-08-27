"""Tests for the keyless scripted reference agent's solver logic.

Each test builds a workspace that mirrors what the platform mounts at /task
(``input/`` populated from the task's ``files/``) and checks the solver writes
exactly what the task's grader expects.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import load_agent_solver

solve = load_agent_solver("scripted-agent")


def _ws(tmp_path: Path, input_files: dict[str, str]) -> Path:
    (tmp_path / "output").mkdir(parents=True, exist_ok=True)
    for rel, content in input_files.items():
        p = tmp_path / "input" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp_path


def _out(ws: Path, rel: str) -> str:
    return (ws / "output" / rel).read_text(encoding="utf-8")


def test_t001_hello_sums_quantities(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {"quantities.csv": "item,quantity\na,10\nb,32\nc,64\nd,36\n"})
    solve.solve(ws, "t001-hello")
    assert _out(ws, "report.txt").strip() == "142"


def test_t002_error_hunt_counts_error_level_lines(tmp_path: Path) -> None:
    ws = _ws(
        tmp_path,
        {"app_events.txt": "ERROR a\nerror b\nINFO c\nERROR d\nErrorX e\nERROR\n"},
    )
    solve.solve(ws, "t002-error-hunt")
    # first token exactly "ERROR": lines 1, 4, 6 -> 3 ("error"/"ErrorX" differ by case)
    assert _out(ws, "report.txt").strip() == "3"


def test_t003_dedupe_keeps_first_occurrence_order(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {"names.txt": "alice\nbob\nalice\ncarol\nbob\ndave\nerin\nalice\n"})
    solve.solve(ws, "t003-dedupe")
    assert _out(ws, "unique.txt") == "alice\nbob\ncarol\ndave\nerin\n"


def test_t004_csv_filter_amount_gt_100(tmp_path: Path) -> None:
    ws = _ws(
        tmp_path,
        {"sales.csv": "region,amount\nnorth,250\nsouth,80\neast,120\nwest,99\neast,100\n"},
    )
    solve.solve(ws, "t004-csv-filter")
    assert _out(ws, "big_sales.csv") == "region,amount\nnorth,250\neast,120\n"


def test_t005_json_deep_merge_b_wins(tmp_path: Path) -> None:
    a = '{"services": {"api": {"port": 8080}, "cache": {"ttl_seconds": 300, "max": 1}}}'
    b = '{"services": {"cache": {"ttl_seconds": 600}, "worker": {"c": 8}}, "debug": true}'
    ws = _ws(tmp_path, {"a.json": a, "b.json": b})
    solve.solve(ws, "t005-json-merge")
    merged = json.loads(_out(ws, "merged.json"))
    assert merged["services"]["cache"]["ttl_seconds"] == 600
    assert merged["services"]["cache"]["max"] == 1  # untouched key survives
    assert merged["services"]["api"]["port"] == 8080
    assert merged["services"]["worker"]["c"] == 8
    assert merged["debug"] is True


def test_t006_log_parse_keeps_exact_error_level(tmp_path: Path) -> None:
    log = (
        "INFO 2026 web up\n"
        "ERROR 2026 db refused\n"
        "error 2026 lowercase ignored\n"
        "ERROR 2026 timeout\n"
    )
    ws = _ws(tmp_path, {"server.log": log})
    solve.solve(ws, "t006-log-parse")
    assert _out(ws, "errors.txt") == "ERROR 2026 db refused\nERROR 2026 timeout\n"


def test_t007_rename_batch_strips_bak_suffix(tmp_path: Path) -> None:
    ws = _ws(
        tmp_path,
        {
            "backup/alpha.txt.bak": "alpha content v1\n",
            "backup/beta.txt.bak": "beta content v2\n",
        },
    )
    solve.solve(ws, "t007-rename-batch")
    assert (ws / "output" / "restored" / "alpha.txt").read_text(encoding="utf-8") == "alpha content v1\n"
    assert (ws / "output" / "restored" / "beta.txt").is_file()
    assert not list((ws / "output" / "restored").glob("*.bak"))


def test_t008_scaffold_creates_empty_files(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {})
    solve.solve(ws, "t008-scaffold")
    for rel in (
        "project/src/main.py",
        "project/tests/test_main.py",
        "project/docs/index.md",
        "project/data/raw/.keep",
        "project/data/processed/.keep",
    ):
        p = ws / "output" / rel
        assert p.is_file() and p.stat().st_size == 0


def test_t009_env_to_json_ignores_comments(tmp_path: Path) -> None:
    env = "# comment\nENV_NAME=production\nPORT=9001\nDATABASE_URL=postgres://hq@10.0.0.9:5432/prod\n"
    ws = _ws(tmp_path, {"config.env": env})
    solve.solve(ws, "t009-env-to-json")
    obj = json.loads(_out(ws, "config.json"))
    assert obj == {
        "ENV_NAME": "production",
        "PORT": "9001",
        "DATABASE_URL": "postgres://hq@10.0.0.9:5432/prod",
    }


def test_t010_placeholder_purge(tmp_path: Path) -> None:
    ws = _ws(
        tmp_path,
        {
            "pages/index.html": "<h1>{{NAME}} home</h1>{{NAME}}",
            "pages/about.html": "about {{NAME}}",
            "pages/contact.html": "hi@{{NAME}}.dev",
        },
    )
    solve.solve(ws, "t010-placeholder-purge")
    for f in ("index.html", "about.html", "contact.html"):
        text = _out(ws, f"site/{f}")
        assert "{{NAME}}" not in text and "Benchworm" in text


def test_t011_longest_line_trimmed_first_on_tie(tmp_path: Path) -> None:
    # both long lines are 24 chars after trimming; the first one wins
    ws = _ws(
        tmp_path,
        {"passage.txt": "short\n  the winning longest line  \ntiny\ntie break loser aaaaaaaa\n"},
    )
    solve.solve(ws, "t011-longest-line")
    assert _out(ws, "longest.txt").strip() == "the winning longest line"


def test_t012_anagram_groups_first_seen_key_order(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {"words.txt": "eat\ntea\ntan\nate\nnat\nbat\nbeta\nbeat\n"})
    solve.solve(ws, "t012-anagram-groups")
    groups = json.loads(_out(ws, "groups.json"))
    assert groups == {
        "aet": ["ate", "eat", "tea"],
        "ant": ["nat", "tan"],
        "abt": ["bat"],
        "abet": ["beat", "beta"],
    }


def test_t013_ini_to_json_coerces_integers(tmp_path: Path) -> None:
    ini = "[server]\nhost = 0.0.0.0\nport = 8443\nworkers = 4\n\n[logging]\nlevel = info\n"
    ws = _ws(tmp_path, {"settings.ini": ini})
    solve.solve(ws, "t013-ini-to-json")
    obj = json.loads(_out(ws, "settings.json"))
    assert obj["server"]["workers"] == 4
    assert obj["server"]["port"] == 8443
    assert obj["server"]["host"] == "0.0.0.0"
    assert obj["logging"]["level"] == "info"


def test_t014_fibonacci_first_20(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {})
    solve.solve(ws, "t014-fibonacci")
    assert _out(ws, "fib.txt") == (
        "0 1 1 2 3 5 8 13 21 34 55 89 144 233 377 610 987 1597 2584 4181"
    )


def test_t015_link_extractor_in_document_order(tmp_path: Path) -> None:
    md = "See [docs](https://example.com/docs) and [faq](https://example.com/faq).\n[c](https://chat.example.dev/join)\n"
    ws = _ws(tmp_path, {"readme.md": md})
    solve.solve(ws, "t015-link-extractor")
    assert _out(ws, "links.txt") == (
        "https://example.com/docs\nhttps://example.com/faq\nhttps://chat.example.dev/join\n"
    )


def test_gaia_computed_answer(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {})
    solve.solve(ws, "g011-square-17")
    assert _out(ws, "answer.txt").strip() == "289"


def test_gaia_table_answer(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {})
    solve.solve(ws, "g002-capital-australia")
    assert _out(ws, "answer.txt").strip().lower() == "canberra"


def test_unknown_task_raises(tmp_path: Path) -> None:
    ws = _ws(tmp_path, {})
    with pytest.raises(KeyError):
        solve.solve(ws, "z999-nonexistent")
