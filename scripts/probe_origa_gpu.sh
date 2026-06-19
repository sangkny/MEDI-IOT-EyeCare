#!/bin/bash
set -euo pipefail
DATASET_ROOT="${DATASET_ROOT:-$HOME/workspace/dataset}"
echo "=== ORIGA / Masks_Square probe ==="
find "$DATASET_ROOT" -maxdepth 5 \( -iname '*origa*' -o -iname '*Masks_Square*' \) 2>/dev/null | head -40
echo "---"
ls -la "$DATASET_ROOT/Glaucoma_extra2" 2>/dev/null | head -20 || true
ls -la "$DATASET_ROOT" 2>/dev/null | head -30 || true
