#!/usr/bin/env bash
set -euo pipefail
for f in alpha beta gamma; do
  if [ ! -f "/task/output/restored/$f.txt" ]; then
    echo "missing /task/output/restored/$f.txt"
    exit 1
  fi
done
if compgen -G "/task/output/restored/*.bak" > /dev/null; then
  echo "found unexpected .bak files in restored/"
  exit 1
fi
if grep -q "alpha content" /task/input/backup/alpha.txt.bak && [ "$(head -c 5 /task/output/restored/alpha.txt)" = "alpha" ]; then
  echo "rename correct"
  exit 0
fi
echo "content check failed"
exit 1
