#!/usr/bin/env bash
# Fundus Lab + SaMD 파트너 API — 호스트 curl (:8001)
set -euo pipefail
BASE="${MEDI_SMOKE_BASE:-http://127.0.0.1:8001}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMG="${MEDI_SMOKE_IMAGE:-$ROOT/uploads/smoke_fundus.jpg}"
if [[ ! -f "$IMG" ]]; then
  python3 -c "
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
p = Path('$IMG')
p.parent.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(0)
img = rng.integers(20, 60, (512, 512, 3), dtype=np.uint8)
pil = Image.fromarray(img)
d = ImageDraw.Draw(pil)
d.ellipse((56, 56, 456, 456), fill=(120, 40, 40))
d.ellipse((226, 226, 286, 286), fill=(30, 30, 30))
pil.save(p, format='JPEG', quality=92)
"
fi

echo "=== health ==="
curl -s "$BASE/health"
echo

echo "=== Fundus Lab comprehensive ==="
curl -s -o /tmp/medi_comp.json -w "HTTP %{http_code}\n" \
  -X POST "$BASE/api/v1/lab/fundus/comprehensive" \
  -F "file=@$IMG;type=image/jpeg" \
  -F "lang=ko" -F "lat=37.5665" -F "lng=126.9780" -F "include_heatmap=true"
head -c 1500 /tmp/medi_comp.json
echo

echo "=== partner register ==="
REG=$(curl -s -X POST "$BASE/api/v1/partner/register" \
  -H "Content-Type: application/json" \
  -d '{"partner_id":"smoke-host","name":"Host Smoke","plan":"trial"}')
echo "$REG"
KEY=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")
B64=$(base64 -w0 <"$IMG" 2>/dev/null || base64 <"$IMG" | tr -d '\n')

echo "=== partner analyze ==="
curl -s -X POST "$BASE/api/v1/partner/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d "{\"partner_id\":\"smoke-host\",\"image_base64\":\"$B64\",\"return_format\":\"json\",\"include_heatmap\":true,\"lang\":\"ko\"}" \
  | head -c 2000
echo
echo "OK host smoke (base=$BASE)"
