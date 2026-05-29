#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API="${API:-http://localhost:8001}"

run_eye() {
  local label="$1" grade_path="$2" out_png="$3"
  curl -sf -X POST "$API/api/v1/lab/fundus/comprehensive" \
    -F "file=@$grade_path" \
    -F "lang=ko" \
    -F "lat=37.5665" \
    -F "lng=126.9780" \
    -F "include_heatmap=true" \
    -o "/tmp/medi_${label}.json"
  python3 - "$label" "$out_png" <<'PY'
import base64, json, sys
label, out_png = sys.argv[1], sys.argv[2]
d = json.load(open(f"/tmp/medi_{label}.json"))
at = d.get("audit_trail", {})
print(f"\n=== {label} ===")
print(f"  DR 등급:      {d['dr_grade']} / 4")
print(f"  신뢰도:       {d['confidence']:.4f}")
print(f"  결정:         {at.get('decision', '?')}")
print(f"  gradcam:      {d.get('gradcam_version')}")
print(f"  attention:    {d.get('attention_score')}")
print(f"  hotspots:     {len(d.get('hotspot_regions', []))}개")
print(f"  heatmap_error:{d.get('heatmap_error')}")
hm = d.get("heatmap_base64") or ""
print(f"  heatmap:      {len(hm)} chars")
if hm:
    raw = base64.b64decode(hm)
    open(out_png, "wb").write(raw)
    print(f"  saved:        {out_png} ({len(raw)} bytes)")
    spots = d.get("hotspot_regions") or []
    if spots:
        print(f"  first_spot:   {spots[0]}")
PY
}

run_eye "left" "data/synthetic/images/test/0/g0_0000.jpg" "heatmap_left_test.png"
run_eye "right" "data/synthetic/images/test/1/g1_0000.jpg" "heatmap_right_test.png"
