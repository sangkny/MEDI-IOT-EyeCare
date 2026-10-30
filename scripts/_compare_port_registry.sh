#!/bin/bash
set -euo pipefail
PC1="/mnt/e/Office_Automation/idea-collection/projects/PORT-ALLOCATION.md"
PC2="/mnt/c/Tools/downloads/phase005-inspect/projects/PORT-ALLOCATION.md"
EXPECTED_PC1="5d97108c4bb335cfd3653ec32d9b7c91302b34f6947f38bee0f4c9f822fed734"
EXPECTED_PC2="8ec6a2908d6379ffde9645addbe1ad7e42926ae6db14056a13a901a5cf181284"

for p in "$PC1" "$PC2"; do
  if [ -f "$p" ]; then
    echo "FOUND $p"
    sha256sum "$p"
    wc -c "$p"
    head -n 12 "$p"
    echo "----"
  else
    echo "MISSING $p"
  fi
done

if [ -f "$PC1" ] && [ -f "$PC2" ]; then
  H1=$(sha256sum "$PC1" | awk '{print tolower($1)}')
  H2=$(sha256sum "$PC2" | awk '{print tolower($1)}')
  echo "PC1_MATCH_EXPECTED $([ "$H1" = "$EXPECTED_PC1" ] && echo YES || echo NO) actual=$H1"
  echo "PC2_MATCH_EXPECTED $([ "$H2" = "$EXPECTED_PC2" ] && echo YES || echo NO) actual=$H2"
  if [ "$H1" = "$H2" ]; then
    echo "REGISTRY_RELATION IDENTICAL"
  else
    echo "REGISTRY_RELATION DIFFERENT"
    echo "PC1_BYTES $(wc -c < "$PC1") PC2_BYTES $(wc -c < "$PC2")"
    echo "--- DIFF HEAD ---"
    diff -u "$PC1" "$PC2" | head -100 || true
  fi
fi
