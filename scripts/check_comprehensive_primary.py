"""
파일명: check_comprehensive_primary.py
목적: check_comprehensive_primary.py 실행 스크립트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
#!/usr/bin/env python3
"""Quick E2E check for primary_concern format."""
import json
import sys
from pathlib import Path

data = json.loads(sys.stdin.read())
oa = data["overall_assessment"]
print("primary_concern:", oa.get("primary_concern"))
print("urgency:", oa.get("referral_urgency"))
print("recommendation:", oa.get("recommendation"))
sc = data.get("screening") or {}
print("urgent_diseases:", sc.get("urgent_diseases"))
print(
    "top_findings:",
    [(f["disease"], f.get("korean_name", ""), f["probability"]) for f in sc.get("top_findings", [])],
)
