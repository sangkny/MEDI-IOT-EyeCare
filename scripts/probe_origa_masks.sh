#!/bin/bash
set -euo pipefail
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
for d in \
  "$DATASET_ROOT/Glaucoma_raw/ORIGA/Masks_Square" \
  "$DATASET_ROOT/Glaucoma_raw/ORIGA/Images" \
  "$DATASET_ROOT/disc_cup_masks/G1020"; do
  echo "=== $d ==="
  ls "$d" 2>/dev/null | head -8 || echo "(missing)"
  echo "count: $(ls "$d" 2>/dev/null | wc -l)"
done
