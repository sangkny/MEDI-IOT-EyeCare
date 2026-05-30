#!/bin/bash
set -euo pipefail
BASE="${BASE:-http://localhost:8001}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

PARTNER_ID="smoke-$(date +%s)"
REGISTER=$(curl -sS -X POST "$BASE/api/v1/partner/register" \
  -H "Content-Type: application/json" \
  -d "{\"partner_id\":\"$PARTNER_ID\",\"name\":\"test-partner\",\"plan\":\"trial\"}")
echo "register: $REGISTER"
API_KEY=$(echo "$REGISTER" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))")

base64 -w0 fundus_right_sklee.jpg > "$TMP/img.b64" 2>/dev/null || base64 fundus_right_sklee.jpg | tr -d '\n' > "$TMP/img.b64"
python3 -c "
import json
payload={
  'partner_id':'$PARTNER_ID',
  'api_key':'$API_KEY',
  'image_base64': open('$TMP/img.b64').read(),
  'analysis_type':'dr',
  'return_format':'json',
  'include_heatmap': True,
  'eye_side':'right',
}
open('$TMP/analyze.json','w').write(json.dumps(payload))
"

curl -sS -X POST "$BASE/api/v1/partner/analyze" \
  -H "Content-Type: application/json" \
  -d @"$TMP/analyze.json" \
  | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('DR',d.get('dr_grade'),'conf',round(d.get('confidence',0),4))
print('lesion',d.get('lesion_labels'),'high_risk',d.get('high_risk_regions'))
print('heatmap',len(d.get('heatmap_base64','')),'cam_res',d.get('cam_resolution'))
at=d.get('audit_trail',{})
print('decision',at.get('decision'),'cost',d.get('cost'))
"
echo "OK partner_smoke"
