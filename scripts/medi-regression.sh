#!/usr/bin/env bash
# MEDI 단계별 회귀 — Docker exec 1회·출력 스트리밍·동시 실행 방지
#
# 사용 (WSL):
#   cd /mnt/e/Office_Automation/idea-collection/projects
#   bash MEDI-IOT-EyeCare/scripts/medi-regression.sh quick
#   bash MEDI-IOT-EyeCare/scripts/medi-regression.sh unit
#   bash MEDI-IOT-EyeCare/scripts/medi-regression.sh core
#   bash MEDI-IOT-EyeCare/scripts/medi-regression.sh full
#
# 모드:
#   quick  ~2min   핵심 스모크 (comprehensive + retinal_cnn + fhir)
#   unit   ~15min  -m unit (84건 목표)
#   core   ~70min  LLM-heavy 3파일 제외 (176건 목표)
#   full   ~2h     tests/ 전체
set -euo pipefail

MODE="${1:-quick}"
PROJECTS_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "${PROJECTS_ROOT}/docker-compose.dev.yml")
LOCK_FILE="${TMPDIR:-/tmp}/medi-pytest.regression.lock"

exec 200>"${LOCK_FILE}"
if ! flock -n 200; then
  echo "[오류] 다른 medi-regression/pytest 가 실행 중입니다. (${LOCK_FILE})"
  echo "       동시 docker compose exec pytest 는 Docker·DB 부하로 hanging 유발 — 1개만 실행하세요."
  exit 1
fi

cd "${PROJECTS_ROOT}"

echo "==> Compose up (medi-iot-api) ..."
"${COMPOSE[@]}" up -d postgres redis medi-iot-api >/dev/null

echo "==> health wait ..."
for i in $(seq 1 30); do
  if "${COMPOSE[@]}" exec -T medi-iot-api curl -sf -o /dev/null http://127.0.0.1:8000/health 2>/dev/null; then
    break
  fi
  [[ "$i" -eq 30 ]] && { echo "[오류] medi-iot-api health timeout"; exit 1; }
  sleep 2
done

run_pytest() {
  # tail/head 파이프 금지 — 진행 상황이 보이도록 stdout 직접 연결
  "${COMPOSE[@]}" exec -T medi-iot-api python -m pytest "$@"
}

case "${MODE}" in
  quick)
    echo "==> quick (~2min): comprehensive + retinal_cnn + fhir ..."
    run_pytest \
      tests/test_comprehensive_fundus.py \
      tests/test_retinal_cnn.py \
      tests/test_fhir_export.py \
      -q --tb=line --durations=10
    ;;
  unit)
    echo "==> unit (~15min): -m unit ..."
    run_pytest tests/ -m unit -q --tb=line --durations=15
    ;;
  core)
    echo "==> core (~70min): LLM-heavy 3 suites ignored ..."
    run_pytest tests/ \
      --ignore=tests/test_images.py \
      --ignore=tests/test_knowledge_base.py \
      --ignore=tests/test_patient_history.py \
      -q --tb=line --durations=20
    ;;
  full)
    echo "==> full (~2h): tests/ 전체 ..."
    run_pytest tests/ -q --tb=line --durations=25
    ;;
  *)
    echo "Usage: $0 {quick|unit|core|full}"
    exit 2
    ;;
esac

echo ""
echo "[완료] medi-regression mode=${MODE}"
