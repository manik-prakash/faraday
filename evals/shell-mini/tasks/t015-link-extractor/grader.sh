#!/usr/bin/env bash
set -euo pipefail
expected="https://example.com/docs
https://example.com/faq
https://chat.example.dev/join
https://git.example.org/mirror/bench"
actual="$(cat /task/output/links.txt)"
if [ "$actual" != "$expected" ]; then
  echo "MISMATCH. got:"
  echo "$actual"
  exit 1
fi
echo "links correct"
