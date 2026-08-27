#!/usr/bin/env bash
set -euo pipefail
expected="alice
bob
carol
dave
erin"
actual="$(cat /task/output/unique.txt)"
if [ "$actual" != "$expected" ]; then
  echo "MISMATCH. got:"
  echo "$actual"
  exit 1
fi
echo "dedupe correct"
