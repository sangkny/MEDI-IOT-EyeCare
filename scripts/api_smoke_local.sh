#!/bin/bash
set -euo pipefail
BASE="${BASE:-http://localhost:8001}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== IoT HealthKit ==="
curl -sf -X POST "$BASE/api/v1/iot/healthkit" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P001","blood_glucose":126,"unit":"mg/dL","timestamp":"2026-05-30T08:00:00Z"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('status',d.get('status'),'ontology',d.get('ontology_passed'),'fhir',d.get('fhir_resource',{}).get('resourceType'))"

echo "=== IoT Health Connect ==="
curl -sf -X POST "$BASE/api/v1/iot/health-connect" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"P001","records":[{"type":"BloodGlucoseRecord","value":126,"unit":"mg/dL","time":"2026-05-30T08:00:00Z"}]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('records',d.get('processed_count'),'status',d.get('status'))"

echo "=== IoT latest ==="
curl -sf "$BASE/api/v1/iot/latest/P001" | python3 -m json.tool | head -12

echo "=== Fundus Lab UI ==="
curl -sf "$BASE/api/v1/lab/fundus" | head -3 || echo "fundus path check"

echo "=== OpenAPI ==="
python3 <<'PY'
import json, urllib.request
d = json.load(urllib.request.urlopen("http://localhost:8001/openapi.json"))
paths = d.get("paths", {})
print(f"총 {len(paths)}개 엔드포인트")
for path in sorted(paths):
    methods = " ".join(m.upper() for m in paths[path])
    print(f"  {methods:12s} {path}")
PY

echo "=== Partner API ==="
REGISTER=$(curl -sf -X POST "$BASE/api/v1/partner/register" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-partner","plan":"basic"}')
PARTNER_ID=$(echo "$REGISTER" | python3 -c "import sys,json; print(json.load(sys.stdin).get('partner_id',''))")
API_KEY=$(echo "$REGISTER" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))")
echo "Partner: $PARTNER_ID"
IMG=$(base64 -w0 fundus_right_sklee.jpg 2>/dev/null || base64 fundus_right_sklee.jpg | tr -d '\n')
curl -sf -X POST "$BASE/api/v1/partner/analyze" \
  -H "Content-Type: application/json" \
  -d "{\"partner_id\":\"$PARTNER_ID\",\"api_key\":\"$API_KEY\",\"image_base64\":\"$IMG\",\"analysis_type\":\"dr\",\"return_format\":\"json\",\"include_heatmap\":true,\"eye_side\":\"right\"}" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
at=d.get('audit_trail',{})
print('DR',d.get('dr_grade'),'conf',round(d.get('confidence',0),4))
print('lesion',d.get('lesion_labels'),'high_risk',d.get('high_risk_regions'))
print('heatmap',len(d.get('heatmap_base64','')),'cam_res',d.get('cam_resolution'),'cost',d.get('cost'))
"

echo "OK api_smoke_local"
