#!/usr/bin/env bash
set -euo pipefail
for f in index.html about.html contact.html; do
  p="/task/output/site/$f"
  [ -f "$p" ] || { echo "missing $p"; exit 1; }
  if grep -qF "{{NAME}}" "$p"; then
    echo "$f still contains placeholder"
    exit 1
  fi
  if ! grep -q "Benchworm" "$p"; then
    echo "$f missing replacement text"
    exit 1
  fi
done
echo "placeholders replaced correctly"
