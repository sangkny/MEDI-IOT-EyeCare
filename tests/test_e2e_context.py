# MEDI-IOT-EyeCare/tests/test_e2e_context.py
# pyright: reportMissingImports=false
# basedpyright: reportMissingImports=false
"""
청킹 도입 Step 2 (book §16.10.2) — MEDI E2E 컨텍스트 회귀.

이 파일은 ``medi-iot-api-dev`` 컨테이너 안에서만 실행되도록 설계되었으며,
런타임 의존성(``httpx``)은 컨테이너 ``requirements.txt`` 에서만 설치된다.
호스트 IDE 분석기(basedpyright)는 venv 가 없어 ``reportMissingImports`` 를
발생시키므로 파일 상단 디렉티브로 이 파일에 한해 끈다.

목적:
    1. ``ORCH_COMPACT_CONTEXT`` 가 켜진 상태에서 실제 LM Studio 진단 호출이
       ``400 Context size has been exceeded`` 없이 완료되는지 확인.
    2. Step 1 (``services/report_gen.py``) 에서 추가한 한 줄 구조화 로그
       ``medi_diagnosis_context`` 가 ``chunking_*`` 키와 함께 발현되는지 확인.

실행:
    # LM Studio 가동 + gemma-4-e4b/26b-a4b 로딩 가정
    docker compose -f projects/docker-compose.dev.yml exec medi-iot-api \\
        pytest -v tests/test_e2e_context.py

skip 규칙:
    - LM Studio ``/v1/models`` 가 200 응답이 아니거나, MEDI ``/health/detail``
      의 ``checks.llm.status != ok`` 이면 자동 skip → CI 무중단.

기존 ``test_e2e.py::TestAIDiagnosis::test_ai_diagnosis_pipeline`` 와 시나리오는
유사하지만, **컨텍스트 한도**와 **새 메트릭 로그** 에 초점을 맞춘 별도 회귀이다.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_llm]

# ── 공통 ──
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"
TIMEOUT = httpx.Timeout(60.0)
AI_ANALYZE_TIMEOUT = httpx.Timeout(900.0, connect=30.0)  # 로컬 LLM 5분+ 여유

# LM Studio 도달 가능 여부 — 컨테이너 환경변수와 동일한 기본값을 사용한다.
LM_STUDIO_BASE = os.getenv("LLM_BASE_URL", "http://host.docker.internal:8000/v1")


def _lm_studio_alive() -> bool:
    """LM Studio ``/v1/models`` 가 200 + ``data[]`` 비어있지 않은지 확인."""
    try:
        r = httpx.get(f"{LM_STUDIO_BASE}/models", timeout=2.0)
        if r.status_code != 200:
            return False
        body = r.json() or {}
        return bool(body.get("data"))
    except Exception:
        return False


def _medi_llm_healthy() -> bool:
    """MEDI API 의 ``/health/detail`` 이 LLM 연결을 OK 로 보고하는지."""
    try:
        r = httpx.get(f"{BASE_URL}/health/detail", timeout=5.0)
        if r.status_code != 200:
            return False
        return (r.json() or {}).get("checks", {}).get("llm", {}).get("status") == "ok"
    except Exception:
        return False


_SKIP_REASON = (
    "LM Studio 미가동 또는 MEDI /health/detail 의 LLM status != ok — "
    "book §16.10.2 절차에 따라 호스트에서 LM Studio 가동 후 다시 실행하세요."
)

requires_lm_studio = pytest.mark.skipif(
    not (_lm_studio_alive() and _medi_llm_healthy()),
    reason=_SKIP_REASON,
)


def _make_patient_code() -> str:
    return f"C{uuid.uuid4().hex[:6].upper()}"


def _doctor_auth_headers() -> dict[str, str]:
    """기존 ``test_e2e.py`` 와 동일한 doctor JWT 발급."""
    r = httpx.post(
        f"{API_V1}/auth/token",
        data={"username": "doctor", "password": "doc123"},
        timeout=60.0,
    )
    assert r.status_code == 200, f"JWT 발급 실패: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# MEDI 입력 스키마 한도 — 모두 Pydantic ``max_length`` 로 보호되고 있다.
# 큰 컨텍스트 스트레스는 LLM 파이프라인 내부(Generator 응답 + RAG 컨텍스트 누적)
# 에서 자연 발생한다. 이 한도들은 외부 입력의 안전선이므로 그대로 따라간다.
_RAW_FINDINGS_MAX = 5000
_ADDITIONAL_CONTEXT_MAX = 1000


def _build_additional_context(*, fill_ratio: float = 0.9) -> str:
    """``additional_context`` Pydantic 한도 안에서 임상 메모를 채운다."""
    unit = (
        "임상 메모: 환자는 다년간 추적 관찰 대상으로, 합병증 발현 가능성이 높다. "
    )
    cap = max(1, int(_ADDITIONAL_CONTEXT_MAX * fill_ratio))
    repeats = max(1, cap // max(1, len(unit)))
    text = unit * repeats
    if len(text) > _ADDITIONAL_CONTEXT_MAX:
        text = text[:_ADDITIONAL_CONTEXT_MAX]
    return text


def _create_patient_and_exam(*, raw_findings_padding: int = 0) -> tuple[str, str]:
    """
    청킹 회귀용 환자 + 검사 생성.

    ``raw_findings_padding`` 은 base + (pad * N) 의 N. 결과 길이가 ``_RAW_FINDINGS_MAX``
    를 넘지 않도록 자동 자른다. 이보다 큰 컨텍스트가 필요하면 ``additional_context``
    쪽을 키워 진단 호출 시점에 task 토큰을 키워야 한다.
    """
    pcode = _make_patient_code()
    p = httpx.post(
        f"{API_V1}/patients/",
        json={"patient_code": pcode, "primary_diagnosis_code": "H36.0"},
        timeout=TIMEOUT,
    )
    assert p.status_code == 201, f"환자 등록 실패: {p.text}"
    patient_id = p.json()["id"]

    base_findings = (
        "우안 후극부: 황반 주위 5개 이상의 점상출혈과 경성삼출물 관찰. "
        "시신경 유두 주위 신생혈관 의심. 정맥 확장 소견. "
        "좌안: 경미한 배경 당뇨망막병증 소견."
    )
    raw_findings = base_findings
    if raw_findings_padding > 0:
        pad = (
            "추가 임상 메모: 환자는 최근 6개월간 시야 흐림 호소, "
            "야간 운전 시 빛 번짐 증가, 중심부 시야 흐려짐의 점진적 악화 보고. "
        )
        raw_findings = base_findings + "\n\n" + (pad * raw_findings_padding)
        # Pydantic max_length=5000 보호
        if len(raw_findings) > _RAW_FINDINGS_MAX:
            raw_findings = raw_findings[:_RAW_FINDINGS_MAX]

    e = httpx.post(
        f"{API_V1}/diagnosis/exam",
        json={
            "patient_id": patient_id,
            "exam_type": "fundus",
            "exam_date": str(date.today()),
            "icd_code": "H36.0",
            "iop_left": 16.0,
            "iop_right": 15.5,
            "raw_findings": raw_findings,
        },
        timeout=TIMEOUT,
    )
    assert e.status_code == 201, f"검사 등록 실패: {e.text}"
    return patient_id, e.json()["id"]


def _assert_no_context_overflow(response_text: str, diagnosis_body: dict) -> None:
    """응답 본문 어디에도 ``Context size`` 등의 오버플로 키워드가 없어야 한다."""
    haystacks = [response_text, str(diagnosis_body)]
    forbidden = ("context size", "context length", "context size has been exceeded")
    for h in haystacks:
        low = (h or "").lower()
        for kw in forbidden:
            assert kw not in low, f"컨텍스트 초과 흔적 발견: '{kw}' 가 응답에 포함됨"


# ReportGenerator 가 Orchestrator 실패 시 폴백으로 채워넣는 placeholder.
# 이 문자열이 응답 ``report`` 로 떨어지면 LM 호출 중 어떤 단계가 실패한 것이다.
_REPORT_FAILURE_PLACEHOLDER = "보고서 생성 실패"


def _build_diagnostic_failure_message(body: dict) -> str:
    """진단 실패 시 디버깅 친화적 메시지 — 호출자가 Step 3/Step 6 로드맵을 참조하게."""
    report = body.get("report") or ""
    return (
        "보고서 생성이 실패 상태로 떨어졌습니다 "
        f"(report={report!r}, llm_iterations={body.get('llm_iterations')}, "
        f"llm_latency_ms={body.get('llm_latency_ms')}, "
        f"ontology_passed={body.get('ontology_passed')}).\n"
        "- docker logs medi-iot-api-dev 에서 'Context size has been exceeded' 또는 "
        "agent.{reviewer|generator|critic} 의 ERROR 로그를 확인하세요.\n"
        "- 발생 시 § 16.10.4 의 'Context overflow 재발 = 0건' 합격선 위반이며, "
        "Step 3 (호출자별 run_chunked_prompt 도입) / Step 6 (LLM 요약 레이어) 도입 후 "
        "PASS 로 전환됩니다."
    )


# ════════════════════════════════════════════════════════════
# 회귀 시나리오
# ════════════════════════════════════════════════════════════


@requires_lm_studio
def test_short_diagnosis_yields_report_without_context_overflow(caplog: pytest.LogCaptureFixture) -> None:
    """
    짧은 입력으로 AI 진단 → 보고서 ≥ 200자, 컨텍스트 초과 0건,
    가능하면 ``medi_diagnosis_context`` 로그가 ``chunking_*`` 키와 함께 한 번 이상 발현.

    pytest 는 medi-iot-api-dev 컨테이너 안에서 돌지만, uvicorn worker 는 별도 프로세스라
    caplog 로 잡히지 않을 가능성이 크다 — 그런 경우는 docker logs 검증에 위임한다.
    """
    _, exam_id = _create_patient_and_exam(raw_findings_padding=0)

    caplog.set_level(logging.INFO, logger="services.report_gen")
    r = httpx.post(
        f"{API_V1}/diagnosis/ai-analyze",
        headers=_doctor_auth_headers(),
        json={
            "exam_id": exam_id,
            "additional_context": "환자 HbA1c 8.2%, 당뇨병 12년차, 인슐린 치료 중",
            "strategy": "consensus",
        },
        timeout=AI_ANALYZE_TIMEOUT,
    )
    assert r.status_code == 201, f"AI 진단 실패: {r.text[:400]}"
    body = r.json()
    _assert_no_context_overflow(r.text, body)

    report = body.get("report") or ""
    assert _REPORT_FAILURE_PLACEHOLDER not in report, _build_diagnostic_failure_message(body)
    assert len(report) >= 200, f"보고서가 너무 짧음: {len(report)}자 — body={body}"

    # Step 1 의 한 줄 로그 검증 — 같은 프로세스에서 잡힐 때만 추가 확인 수행.
    ctx_records = [
        rec for rec in caplog.records if rec.getMessage() == "medi_diagnosis_context"
    ]
    if ctx_records:
        rec = ctx_records[-1]
        assert getattr(rec, "flow", None) == "medi_diagnosis"
        assert getattr(rec, "strategy", None) == "consensus"
        assert getattr(rec, "chunking_model", "") != ""
        assert hasattr(rec, "chunking_fits_context")
        assert hasattr(rec, "chunking_chunks_needed")
    # else: 별도 프로세스라 caplog 가 비어있을 수 있음 → docker logs 확인에 위임.


@pytest.mark.xfail(
    strict=False,
    reason=(
        "운영 환경 의존성: LM Studio 가 HEAVY 모델(gemma-4-26b-a4b)을 약 1K 미만 "
        "num_ctx 로 로딩한 환경에서는 패딩 입력 stress 시 fit 시키기 어렵다. "
        "운영자가 LM Studio 모델 컨텍스트를 ≥ 4096 으로 늘리거나, Step 6 의 "
        "LLM 요약 레이어 도입 후 PASS 로 자동 전환된다 — strict=False 라 PASS 시 "
        "xpassed 알림이 떠 회귀 해소를 즉시 감지할 수 있다."
    ),
)
@requires_lm_studio
def test_padded_diagnosis_keeps_report_under_context_budget() -> None:
    """
    additional_context 를 키운 케이스 → 분석상 분할 권장이 떠도 보고서 ≥ 200자,
    LM Studio 가 ``Context size exceeded`` 를 던지지 않아야 한다.

    ``raw_findings`` 는 Pydantic max_length=5000 한도 안에서만 패딩한다.
    실제 컨텍스트 스트레스는 ``additional_context`` 의 반복으로 만든다.

    회귀 의미: Step 3 에서 짧은 입력 케이스는 PASS 로 전환되었지만, LM Studio
    호스트 모델이 매우 작은 num_ctx(현장 측정 시 약 800~1000 토큰)로 로딩될 때
    여전히 fail 한다. 운영자가 모델 컨텍스트를 늘리는 것이 진짜 해결책이며,
    Step 6(LLM 요약 레이어) 가 들어오면 코드 측에서도 PASS 가능해진다.
    """
    _, exam_id = _create_patient_and_exam(raw_findings_padding=25)
    r = httpx.post(
        f"{API_V1}/diagnosis/ai-analyze",
        headers=_doctor_auth_headers(),
        json={
            "exam_id": exam_id,
            "additional_context": _build_additional_context(fill_ratio=0.9),
            "strategy": "consensus",
        },
        timeout=AI_ANALYZE_TIMEOUT,
    )
    assert r.status_code == 201, f"AI 진단 실패: {r.text[:400]}"
    body = r.json()
    _assert_no_context_overflow(r.text, body)

    report = body.get("report") or ""
    assert _REPORT_FAILURE_PLACEHOLDER not in report, _build_diagnostic_failure_message(body)
    assert len(report) >= 200, f"보고서가 너무 짧음: {len(report)}자 — body={body}"
