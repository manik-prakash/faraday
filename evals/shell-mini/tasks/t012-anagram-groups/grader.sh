#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import json

with open("/task/output/groups.json") as fh:
    groups = json.load(fh)

expected = {
    "aet": ["ate", "eat", "tea"],
    "ant": ["nat", "tan"],
    "abt": ["bat"],
    "abet": ["beat", "beta"],
}
if groups != expected:
    print("MISMATCH")
    print(json.dumps(groups, indent=2))
    raise SystemExit(1)
print("anagram groups correct")
PY
