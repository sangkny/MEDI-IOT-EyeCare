"""
파일명: check_v10_dr_paths.py
목적: check_v10_dr_paths.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
#!/usr/bin/env python3
"""unified_v10.json DR 경로 검증 (GPU)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "training/manifests/unified_v10.json"
if not manifest.is_file():
    print(f"FAIL: {manifest} not found")
    sys.exit(1)

data = json.loads(manifest.read_text(encoding="utf-8"))
dr_samples = [
    s
    for s in data["samples"]
    if "dr" in s.get("available_labels", {})
    and len(s.get("available_labels", {})) == 1
]
print(f"DR-only samples={len(dr_samples)}")
if dr_samples:
    print(f"first path={dr_samples[0]['path']}")
resized = sum(1 for s in dr_samples if "resized_cache" in s["path"])
print(f"resized_cache={resized}/{len(dr_samples)}")
print(f"data_dir={data.get('data_dir')} dr_data_dir={data.get('dr_data_dir')}")
if dr_samples and resized < len(dr_samples):
    sys.exit(2)
