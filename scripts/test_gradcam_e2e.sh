#!/bin/bash
# GradCAM++ E2E — sklee 실제 이미지 + 원본 해상도 히트맵 검증
set -euo pipefail
IMG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API="${API:-http://localhost:8001}"

for eye in left right; do
  img="${IMG_DIR}/fundus_${eye}_sklee.jpg"
  if [[ ! -f "$img" ]]; then
    echo "SKIP ${eye}: $img not found"
    continue
  fi
  echo "=== ${eye}안 ==="
  curl -sf -X POST "${API}/api/v1/lab/fundus/comprehensive" \
    -F "file=@${img}" \
    -F "include_heatmap=true" \
    -F "eye_side=${eye}" \
    -F "lang=ko" \
    -F "lat=37.5665" \
    -F "lng=126.9780" \
    -o "/tmp/medi_${eye}_v2.json"

  python3 - "$eye" "$IMG_DIR" <<'PY'
import base64, json, os, sys
eye, img_dir = sys.argv[1], sys.argv[2]
d = json.load(open(f"/tmp/medi_{eye}_v2.json"))
at = d.get("audit_trail", {})
print(f"  DR:           {d['dr_grade']} / 4")
print(f"  신뢰도:       {d['confidence']:.4f}")
print(f"  결정:         {at.get('decision', '?')}")
print(f"  cam 해상도:   {d.get('cam_resolution', '?')}")
print(f"  병변 레이블:  {d.get('lesion_labels', [])}")
print(f"  병변 설명:    {d.get('lesion_description', '')}")
print(f"  고위험 구역:  {d.get('high_risk_regions', [])}")
print(f"  attention:    {d.get('attention_score')}")
hs = d.get("hotspot_regions") or []
print(f"  hotspots:     {len(hs)}개")
for h in hs[:3]:
    print(
        f"    → {h.get('region')} ({h.get('x_px')},{h.get('y_px')}) "
        f"intensity={h.get('intensity', 0):.3f} [{h.get('lesion_type')}]"
    )
hm = d.get("heatmap_base64") or ""
print(f"  heatmap:      {len(hm)} chars")
if hm:
    out = os.path.join(img_dir, f"heatmap_{eye}_v2.jpg")
    raw = base64.b64decode(hm)
    with open(out, "wb") as f:
        f.write(raw)
    print(f"  saved:        {out} ({len(raw):,} bytes)")
    v1 = os.path.join(img_dir, f"heatmap_{eye}_test.png")
    if os.path.isfile(v1):
        print(f"  v1 compare:   {os.path.getsize(v1):,} bytes (224 overlay PNG)")
PY
done
