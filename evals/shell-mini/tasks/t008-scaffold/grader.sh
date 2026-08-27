#!/usr/bin/env bash
set -euo pipefail
for f in \
  project/src/main.py \
  project/tests/test_main.py \
  project/docs/index.md \
  project/data/raw/.keep \
  project/data/processed/.keep; do
  p="/task/output/$f"
  if [ ! -f "$p" ]; then
    echo "missing $p"
    exit 1
  fi
  if [ -s "$p" ]; then
    echo "$p is not empty"
    exit 1
  fi
done
echo "scaffold correct"
