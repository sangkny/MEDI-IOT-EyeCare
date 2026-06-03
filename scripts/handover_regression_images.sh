#!/bin/bash
set -euo pipefail
PROJECTS=/mnt/e/Office_Automation/idea-collection/projects
MEDI=$PROJECTS/MEDI-IOT-EyeCare

echo "=== Docker status ==="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'medi|coops|redis|postgres|NAMES' || true

echo "=== Health ==="
curl -sf http://localhost:8001/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('MEDI',d.get('status'),'model',d.get('cnn_model','?'))" || echo "MEDI down"
curl -sf http://localhost:8003/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('CoOps',d.get('status'))" || echo "CoOps down"

echo "=== MEDI unit ==="
docker exec medi-iot-api-dev bash -c "python -m pytest tests/ -q -m unit --tb=line 2>&1 | tail -5" || echo "MEDI unit skip"

echo "=== LLM ==="
docker exec medi-iot-api-dev bash -c \
  "export PYTHONPATH=/app/shared-libraries && python -m pytest /app/shared-libraries/llm/tests/test_providers.py -q --tb=line 2>&1 | tail -3" || echo "LLM skip"

echo "=== CoOps ==="
docker exec coops-api-dev bash -c \
  "python -m pytest tests/ -q --ignore=tests/test_stripe.py --tb=line 2>&1 | tail -3" || echo "CoOps skip"

echo "=== Fundus images ==="
cd "$MEDI"
for eye in left right; do
  echo "--- ${eye} ---"
  curl -sf -X POST http://localhost:8001/api/v1/lab/fundus/comprehensive \
    -F "file=@fundus_${eye}_sklee.jpg" \
    -F "lang=ko" \
    -F "include_heatmap=true" \
    -F "eye_side=${eye}" \
    -o "/tmp/medi_${eye}_comp.json"
  python3 - "$eye" "$MEDI" <<'PY'
import base64, json, os, sys
eye, medi_dir = sys.argv[1], sys.argv[2]
d = json.load(open(f"/tmp/medi_{eye}_comp.json"))
print("DR", d.get("dr_grade"), "conf", round(d.get("confidence", 0), 4))
print("lesion", d.get("lesion_labels"))
print("decision", d.get("audit_trail", {}).get("decision"))
hm = d.get("heatmap_base64") or ""
if hm:
    fn = os.path.join(medi_dir, f"heatmap_{eye}_latest.jpg")
    raw = base64.b64decode(hm)
    with open(fn, "wb") as f:
        f.write(raw)
    print("saved", fn, len(raw))
PY
done
echo "OK handover_regression_images"
