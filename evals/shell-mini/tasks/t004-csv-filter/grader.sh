#!/usr/bin/env bash
set -euo pipefail
expected="region,amount
north,250
east,120
north,300
south,101
west,540"
actual="$(cat /task/output/big_sales.csv)"
if [ "$actual" != "$expected" ]; then
  echo "MISMATCH. got:"
  echo "$actual"
  exit 1
fi
echo "filter correct"
