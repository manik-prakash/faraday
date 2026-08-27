#!/usr/bin/env bash
set -euo pipefail
expected='ERROR 2026-01-05T09:00:07Z db connection refused
ERROR 2026-01-05T09:01:22Z api upstream timeout after 30s
ERROR 2026-01-05T09:03:45Z worker crashed with code 137
ERROR 2026-01-05T09:06:31Z s3 upload failed retrying'
actual="$(cat /task/output/errors.txt)"
if [ "$actual" != "$expected" ]; then
  echo "MISMATCH. got:"
  echo "$actual"
  exit 1
fi
echo "log parse correct"
