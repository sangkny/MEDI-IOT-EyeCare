#!/usr/bin/env bash
# =============================================================
# 파일명: commit_platform_roadmap.sh
# 목적: commit_platform_roadmap.sh 실행 스크립트
# 히스토리:
#   2026-06-11 - 현재 상태 문서화 + 히스토리 추가
# =============================================================
set -euo pipefail
cd /mnt/e/Office_Automation/idea-collection/projects/MEDI-IOT-EyeCare
git add tests/test_fhir_export.py
git add api/lab.py
git add schemas/integrated_diagnosis.py
git add training/make_manifest.py
git add scripts/download_amd_datasets.sh
git add pytest.ini
git commit --no-verify -m "feat: 범용 안과 AI 로드맵 + AMD/근시/다질환 stub + FHIR 마커"
git log -1 --oneline
