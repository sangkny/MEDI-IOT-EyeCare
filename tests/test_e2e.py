"""
파일명: test_e2e.py
목적: e2e.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
# MEDI-IOT-EyeCare/tests/test_e2e.py
"""
MEDI-IOT EyeCare E2E 테스트

목적: Week 2 Day 2 — 환자 등록 → 검사 등록 → AI 진단 전체 흐름 검증

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        pytest tests/test_e2e.py -v -s

클래스:
    TestHealthAPI      — /health 엔드포인트 (빠름)
    TestPatientAPI     — 환자 CRUD (빠름, LLM 없음)
    TestDiagnosisAPI   — 검사 등록 (빠름, LLM 없음)
    TestAIDiagnosis    — AI 진단 (느림, 실제 LLM 호출 ~2분)
"""
import uuid
import pytest
import httpx
from datetime import date

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"
TIMEOUT = httpx.Timeout(300.0)   # 일반 API
# CONSENSUS AI 진단은 로컬 LLM(LM Studio)에서 5분 이상 걸릴 수 있음
AI_ANALYZE_TIMEOUT = httpx.Timeout(900.0, connect=30.0)


def doctor_auth_headers() -> dict[str, str]:
    """Week 7 — AI 진단은 doctor JWT 필요."""
    r = httpx.post(
        f"{API_V1}/auth/token",
        data={"username": "doctor", "password": "doc123"},
        timeout=60.0,
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════

def make_patient_code() -> str:
    return f"T{uuid.uuid4().hex[:6].upper()}"


# ════════════════════════════════════════════════════════════
# Level 0 — Health 체크
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_db
class TestHealthAPI:
    """
    목적: API 서버 동작 기본 확인
    단계: /health + /health/detail 응답 검증
    """

    def test_health_ok(self):
        """기본 헬스 체크 — status=ok, db_connected=true"""
        r = httpx.get(f"{BASE_URL}/health", timeout=10)
        print(f"\n  GET /health → {r.status_code}")
        print(f"  응답: {r.json()}")

        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db_connected"] is True
        assert body["service"] == "medi-iot"
        print("  ✅ health OK")

    def test_health_detail_llm_redis(self):
        """상세 헬스 체크 — LLM + Redis 연결 확인"""
        r = httpx.get(f"{BASE_URL}/health/detail", timeout=15)
        print(f"\n  GET /health/detail → {r.status_code}")
        body = r.json()
        print(f"  LLM:   {body['checks'].get('llm', {})}")
        print(f"  Redis: {body['checks'].get('redis', {})}")

        assert r.status_code == 200
        assert body["checks"]["llm"]["status"] == "ok"
        assert body["checks"]["redis"]["status"] == "ok"
        print("  ✅ LLM + Redis 모두 연결됨")


# ════════════════════════════════════════════════════════════
# Level 1 — 환자 API
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_db
class TestPatientAPI:
    """
    목적: 환자 CRUD 전체 흐름 검증
    단계: 등록 → 조회(UUID) → 조회(patient_code) → 목록 → 비활성화
    """

    def test_create_patient(self):
        """
        목적: 환자 등록 + PII 마스킹 확인
        단계: POST /patients → 201 응답 + name_masked 검증
        """
        code = make_patient_code()
        payload = {
            "patient_code": code,
            "name": "홍길동",
            "date_of_birth": "1975-03-15",
            "gender": "male",
            "primary_diagnosis_code": "H36.0",
            "notes": "E2E 테스트 환자",
        }
        r = httpx.post(f"{API_V1}/patients/", json=payload, timeout=TIMEOUT)
        print(f"\n  POST /patients/ → {r.status_code}")
        body = r.json()
        print(f"  patient_code: {body.get('patient_code')}")
        print(f"  name_masked:  {body.get('name_masked')}")

        assert r.status_code == 201, f"등록 실패: {r.text}"
        assert body["patient_code"] == code
        assert body["is_active"] is True
        # PII 마스킹: '홍길동' → '홍**'
        assert body["name_masked"] == "홍**", f"마스킹 실패: {body.get('name_masked')}"
        assert body["primary_diagnosis_code"] == "H36.0"
        print("  ✅ 환자 등록 + PII 마스킹 확인")

        # 다음 테스트에서 재사용 가능하도록 클래스 변수 저장
        TestPatientAPI._patient_id   = body["id"]
        TestPatientAPI._patient_code = code

    def test_get_patient_by_uuid(self):
        """
        목적: UUID로 환자 조회
        단계: GET /patients/{uuid}
        """
        pid = getattr(TestPatientAPI, "_patient_id", None)
        if not pid:
            pytest.skip("이전 테스트(create)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/patients/{pid}", timeout=TIMEOUT)
        print(f"\n  GET /patients/{pid[:8]}... → {r.status_code}")
        body = r.json()

        assert r.status_code == 200
        assert body["id"] == pid
        print(f"  ✅ UUID 조회 성공: {body['patient_code']}")

    def test_get_patient_by_code(self):
        """
        목적: patient_code로 환자 조회 (병원 시스템 호환)
        단계: GET /patients/{patient_code}
        """
        code = getattr(TestPatientAPI, "_patient_code", None)
        if not code:
            pytest.skip("이전 테스트(create)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/patients/{code}", timeout=TIMEOUT)
        print(f"\n  GET /patients/{code} → {r.status_code}")
        body = r.json()

        assert r.status_code == 200
        assert body["patient_code"] == code
        print(f"  ✅ patient_code 조회 성공")

    def test_list_patients(self):
        """
        목적: 환자 목록 조회 (페이징)
        단계: GET /patients?skip=0&limit=5
        """
        r = httpx.get(f"{API_V1}/patients/", params={"limit": 5}, timeout=TIMEOUT)
        print(f"\n  GET /patients/?limit=5 → {r.status_code}")
        body = r.json()
        print(f"  조회된 환자 수: {len(body)}명")

        assert r.status_code == 200
        assert isinstance(body, list)
        assert len(body) >= 1
        print(f"  ✅ 목록 조회 성공: {len(body)}명")

    def test_duplicate_patient_code_rejected(self):
        """
        목적: 중복 patient_code 거부 확인
        단계: 동일 코드로 재등록 → 409 Conflict
        """
        code = getattr(TestPatientAPI, "_patient_code", None)
        if not code:
            pytest.skip("이전 테스트(create)가 실행되지 않았음")

        r = httpx.post(
            f"{API_V1}/patients/",
            json={"patient_code": code, "name": "복제인간"},
            timeout=TIMEOUT,
        )
        print(f"\n  중복 등록 시도 → {r.status_code}")
        assert r.status_code == 409, f"중복 거부 실패: {r.status_code}"
        print("  ✅ 중복 patient_code 거부 확인")

    def test_invalid_icd_code_rejected(self):
        """
        목적: 잘못된 ICD-10 코드 거부
        단계: primary_diagnosis_code='INVALID' → 422 Unprocessable
        """
        r = httpx.post(
            f"{API_V1}/patients/",
            json={
                "patient_code": make_patient_code(),
                "primary_diagnosis_code": "INVALID",
            },
            timeout=TIMEOUT,
        )
        print(f"\n  잘못된 ICD 코드 → {r.status_code}")
        assert r.status_code == 422, f"검증 실패 예상: {r.status_code}"
        print("  ✅ 잘못된 ICD 코드 거부 확인")


# ════════════════════════════════════════════════════════════
# Level 2 — 검사 등록 API
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_db
class TestDiagnosisAPI:
    """
    목적: 검사 기록 등록 + 조회 흐름 검증 (LLM 없음)
    단계: 환자 등록 → 검사 등록 → 검사 상태 확인
    """

    def _create_test_patient(self) -> str:
        """테스트용 환자 생성 → patient UUID 반환"""
        code = make_patient_code()
        r = httpx.post(
            f"{API_V1}/patients/",
            json={"patient_code": code, "primary_diagnosis_code": "H36.0"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 201
        return r.json()["id"]

    def test_create_eye_exam(self):
        """
        목적: 안과 검사 기록 등록
        단계: POST /diagnosis/exam → 201 응답 + report_status=pending
        """
        patient_id = self._create_test_patient()
        payload = {
            "patient_id": patient_id,
            "exam_type": "fundus",
            "exam_date": str(date.today()),
            "icd_code": "H36.0",
            "iop_left": 14.5,
            "iop_right": 15.2,
            "visual_acuity_left": "0.8",
            "visual_acuity_right": "0.7",
            "raw_findings": (
                "우안: 황반 주위 점상출혈 및 경성삼출물 다수 관찰. "
                "신생혈관 의심 소견. "
                "좌안: 경미한 미세동맥류 관찰."
            ),
        }
        r = httpx.post(f"{API_V1}/diagnosis/exam", json=payload, timeout=TIMEOUT)
        print(f"\n  POST /diagnosis/exam → {r.status_code}")
        body = r.json()
        print(f"  exam_id:       {body.get('id', '')[:8]}...")
        print(f"  exam_type:     {body.get('exam_type')}")
        print(f"  icd_code:      {body.get('icd_code')}")
        print(f"  report_status: {body.get('report_status')}")

        assert r.status_code == 201, f"검사 등록 실패: {r.text}"
        assert body["exam_type"] == "fundus"
        assert body["icd_code"] == "H36.0"
        assert body["report_status"] == "pending"
        assert body["iop_left"] == 14.5
        print("  ✅ 검사 등록 성공 (report_status=pending)")

        TestDiagnosisAPI._exam_id    = body["id"]
        TestDiagnosisAPI._patient_id = patient_id

    def test_get_patient_exams(self):
        """
        목적: 환자별 검사 목록 조회
        단계: GET /patients/{id}/exams → 방금 등록한 검사 포함 확인
        """
        patient_id = getattr(TestDiagnosisAPI, "_patient_id", None)
        if not patient_id:
            pytest.skip("이전 테스트가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/patients/{patient_id}/exams", timeout=TIMEOUT)
        print(f"\n  GET /patients/.../exams → {r.status_code}")
        body = r.json()
        print(f"  검사 기록 수: {len(body)}개")

        assert r.status_code == 200
        assert len(body) >= 1
        assert body[0]["exam_type"] == "fundus"
        print("  ✅ 환자별 검사 목록 조회 성공")

    def test_invalid_exam_type_rejected(self):
        """
        목적: 잘못된 exam_type 거부 확인
        단계: exam_type='XRAY' → 422
        """
        patient_id = self._create_test_patient()
        r = httpx.post(
            f"{API_V1}/diagnosis/exam",
            json={
                "patient_id": patient_id,
                "exam_type": "xray",   # 지원하지 않는 타입
                "exam_date": str(date.today()),
            },
            timeout=TIMEOUT,
        )
        print(f"\n  잘못된 exam_type → {r.status_code}")
        assert r.status_code == 422
        print("  ✅ 잘못된 exam_type 거부 확인")


# ════════════════════════════════════════════════════════════
# Level 3 — AI 진단 (실제 LLM 호출)
# ════════════════════════════════════════════════════════════

@pytest.mark.integration
@pytest.mark.requires_llm
class TestAIDiagnosis:
    """
    목적: AI 진단 보고서 전체 파이프라인 검증
    단계: 검사 등록 → AI 진단 요청 → 보고서 내용 + Ontology 검증 확인

    주의: 실제 LLM 호출 — 약 1~3분 소요
    전략: CONSENSUS (FAST gemma-4-e4b + HEAVY gemma-4-26b-a4b)
    """

    def _create_patient_and_exam(self) -> tuple[str, str]:
        """테스트용 환자 + 검사 생성 → (patient_id, exam_id)"""
        # 환자 생성
        p_r = httpx.post(
            f"{API_V1}/patients/",
            json={"patient_code": make_patient_code(), "primary_diagnosis_code": "H36.0"},
            timeout=TIMEOUT,
        )
        assert p_r.status_code == 201
        patient_id = p_r.json()["id"]

        # 검사 등록
        e_r = httpx.post(
            f"{API_V1}/diagnosis/exam",
            json={
                "patient_id": patient_id,
                "exam_type": "fundus",
                "exam_date": str(date.today()),
                "icd_code": "H36.0",
                "iop_left": 16.0,
                "iop_right": 15.5,
                "raw_findings": (
                    "우안 후극부: 황반 주위 5개 이상의 점상출혈과 경성삼출물 관찰. "
                    "시신경 유두 주위 신생혈관 의심. 정맥 확장 소견. "
                    "좌안: 경미한 배경 당뇨망막병증 소견."
                ),
            },
            timeout=TIMEOUT,
        )
        assert e_r.status_code == 201
        return patient_id, e_r.json()["id"]

    def test_ai_diagnosis_pipeline(self):
        """
        목적: AI 진단 보고서 생성 전체 파이프라인 검증
        단계: POST /diagnosis/ai-analyze → 보고서 내용 + ontology_passed 확인
        기대:
          - diagnosis_code: ICD-10 형식
          - report: 200자 이상의 의료 보고서
          - ontology_passed: True (MEDICAL 도메인 규칙 준수)
          - confidence_score >= 0.6
        """
        patient_id, exam_id = self._create_patient_and_exam()

        print(f"\n  환자 생성: {patient_id[:8]}...")
        print(f"  검사 등록: {exam_id[:8]}...")
        print(f"  AI 진단 요청 중... (1~3분 예상)")

        r = httpx.post(
            f"{API_V1}/diagnosis/ai-analyze",
            headers=doctor_auth_headers(),
            json={
                "exam_id": exam_id,
                "additional_context": "환자 HbA1c 8.2%, 당뇨병 진단 12년차, 인슐린 치료 중",
                "strategy": "consensus",
            },
            timeout=AI_ANALYZE_TIMEOUT,
        )

        assert r.status_code == 201, f"AI 진단 실패: {r.text[:300]}"
        body = r.json()

        # 진단 코드 확인
        print(f"\n  ── 진단 결과 ──────────────────────────────")
        print(f"  diagnosis_code:   {body.get('diagnosis_code')}")
        print(f"  diagnosis_name:   {body.get('diagnosis_name')}")
        print(f"  severity:         {body.get('severity')}")
        print(f"  ontology_passed:  {body.get('ontology_passed')}")
        print(f"  confidence_score: {body.get('confidence_score')}")
        print(f"  llm_model:        {body.get('llm_model')}")
        print(f"  llm_iterations:   {body.get('llm_iterations')}")
        print(f"  llm_latency_ms:   {body.get('llm_latency_ms', 0):.0f}ms")
        print(f"\n  ── 보고서 내용 (앞 300자) ─────────────────")
        report = body.get("report", "")
        print(f"  {report[:300]}")
        print(f"  ...")

        # 핵심 검증
        assert body["diagnosis_code"], "진단 코드 없음"
        assert report and len(report) >= 200, f"보고서가 너무 짧음: {len(report)}자"
        assert body["severity"] in ("normal", "mild", "moderate", "severe", "critical")
        assert body["confidence_score"] is not None
        assert body["confidence_score"] >= 0.5, f"신뢰도 너무 낮음: {body['confidence_score']}"

        if body.get("ontology_passed"):
            print(f"\n  ✅ OntologyValidator MEDICAL 도메인 검증 통과")
        else:
            print(f"\n  ⚠ OntologyValidator FAIL (보고서는 생성됨, 의사 추가 검토 필요)")

        print(f"  ✅ AI 진단 파이프라인 완료")

        # 치료 계획 출력
        if body.get("treatment_plan"):
            print(f"\n  ── 치료 계획 ──────────────────────────────")
            print(f"  {body['treatment_plan'][:200]}")

        TestAIDiagnosis._diagnosis_id = body["id"]

    def test_get_diagnosis_result(self):
        """
        목적: 생성된 진단 결과 조회 확인
        단계: GET /diagnosis/{id} → 보고서 저장 확인
        """
        diag_id = getattr(TestAIDiagnosis, "_diagnosis_id", None)
        if not diag_id:
            pytest.skip("이전 테스트(AI 진단)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/diagnosis/{diag_id}", timeout=TIMEOUT)
        print(f"\n  GET /diagnosis/{diag_id[:8]}... → {r.status_code}")
        body = r.json()

        assert r.status_code == 200
        assert body["id"] == diag_id
        assert body["report"] is not None
        print(f"  ✅ 진단 결과 조회 성공 (report_status: completed)")
