# MEDI-IOT-EyeCare/tests/conftest.py
"""
E2E 테스트 공유 픽스처

전략:
  - 실제 실행 중인 API 서버(localhost:8000)에 httpx로 HTTP 요청
  - DB 격리: 테스트마다 고유 patient_code(uuid prefix) 사용
  - TestAIDiagnosis: 실제 LLM 호출 (slow, 1~3분 예상)
"""
import uuid
import pytest
import httpx

BASE_URL = "http://localhost:8000"
API_V1   = f"{BASE_URL}/api/v1"


@pytest.fixture(scope="session")
def client():
    """동기 httpx 클라이언트 (세션 전체 공유)"""
    with httpx.Client(base_url=BASE_URL, timeout=300.0) as c:
        yield c


@pytest.fixture(scope="session")
def api_url():
    return API_V1


@pytest.fixture
def unique_patient_code():
    """테스트마다 고유한 환자 코드 생성"""
    return f"T{uuid.uuid4().hex[:6].upper()}"
