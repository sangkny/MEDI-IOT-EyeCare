#!/usr/bin/env bash
# GitHub Actions / 로컬 CI 동일 pytest 진입점 (ONNX·LM Studio 제외)
set -euo pipefail
cd "$(dirname "$0")/.."
curl -sf --max-time 5 http://127.0.0.1:8000/health >/dev/null || { echo "API not reachable before pytest"; exit 1; }
python -m pytest tests/ -q \
  --ignore=tests/test_retinal_cnn.py \
  --ignore=tests/test_inference_router.py \
  --ignore=tests/test_e2e_week4_full_flow.py \
  --ignore=tests/test_knowledge_base.py \
  -k 'not test_health_detail_llm_redis and not test_ai_diagnosis_pipeline and not test_analyze_uploaded_image and not test_auto_analyze_on_upload and not TestReportGenDiabetic and not TestReportGenGlaucoma and not TestEyeAnalyzerToReport' \
  --tb=short
