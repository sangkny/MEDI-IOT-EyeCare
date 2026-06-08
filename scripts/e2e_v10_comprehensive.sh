#!/usr/bin/env bash
# v10 comprehensive E2E — sklee 좌/우안 + 응답시간
set -euo pipefail
API="${MEDI_API_URL:-http://localhost:8001}"
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"

run_one() {
  local eye="$1" file="$2"
  echo "=== eye=$eye file=$(basename "$file") ==="
  local t0=$(date +%s%N)
  local resp
  resp=$(curl -s -X POST "$API/api/v1/lab/fundus/comprehensive" \
    -F "file=@$file" \
    -F "patient_id=sklee" \
    -F "eye=$eye" \
    -F "include_heatmap=false")
  local t1=$(date +%s%N)
  local ms=$(( (t1 - t0) / 1000000 ))
  python3 -c "
import json,sys
d=json.loads(sys.argv[1])
dr=d['dr']; gl=d.get('glaucoma') or {}; am=d.get('amd') or {}; my=d.get('myopia') or {}
sc=d.get('screening') or {}; oa=d.get('overall_assessment') or {}
fmt=d.get('input_format','?')
print(f'format={fmt} elapsed_ms={sys.argv[2]}')
print(f'DR:    grade={dr.get(\"grade\", dr.get(\"dr_grade\"))} conf={dr.get(\"confidence\",0):.3f} {dr.get(\"decision\")}')
if gl:
  cdr=(gl.get('cup_disc_ratio') or {}).get('value')
  print(f'GL:    prob={gl.get(\"probability\",0):.3f} CDR={cdr} {gl.get(\"decision\")}')
if am:
  print(f'AMD:   prob={am.get(\"probability\",0):.3f} {am.get(\"decision\")}')
if my:
  print(f'MYO:   prob={my.get(\"probability\",0):.3f} {my.get(\"decision\")}')
print(f'Screen: urgent={sc.get(\"urgent_diseases\")}')
print(f'Overall: {oa.get(\"primary_concern\")} {oa.get(\"referral_urgency\")}')
" "$resp" "$ms"
}

run_one right "$REPO/fundus_right_sklee.jpg"
run_one left "$REPO/fundus_left_sklee.jpg"
