# MEDI-IOT-EyeCare/tests/test_images.py
"""
이미지 업로드 API + pgvector 테스트 [Week 3]

목적: 이미지 업로드 → 저장 → VISION 분석 → 결과 조회 흐름 검증

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        pytest tests/test_images.py -v -s

클래스:
    TestPgvector        — pgvector 확장 + 벡터 저장 검증 (DB 직접)
    TestImageUploadAPI  — 이미지 업로드 엔드포인트 테스트
    TestImageAnalysis   — VISION 모델 이미지 분석 테스트 (LLM 호출)
"""
import io
import sys
import asyncio
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")

BASE_URL = "http://localhost:8000"
API_V1   = f"{BASE_URL}/api/v1"
TIMEOUT  = httpx.Timeout(120.0)


def _async_db_url() -> str:
    from config import get_settings

    url = get_settings().database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


# ════════════════════════════════════════════════════════════
# 헬퍼
# ════════════════════════════════════════════════════════════

def _make_test_jpeg(size_kb: int = 10) -> bytes:
    """테스트용 더미 JPEG 이미지 생성 (최소 유효 JPEG 헤더)"""
    # 최소 유효 JPEG 파일 (SOI + APP0 + EOI)
    jpeg_header = (
        b"\xff\xd8\xff\xe0"           # SOI + APP0 marker
        b"\x00\x10"                   # APP0 length
        b"JFIF\x00"                   # identifier
        b"\x01\x01"                   # version
        b"\x00"                       # aspect ratio units
        b"\x00\x01\x00\x01"           # X, Y density
        b"\x00\x00"                   # thumbnail size
        + b"\x00" * max(0, size_kb * 1024 - 20)  # padding
        + b"\xff\xd9"                 # EOI
    )
    return jpeg_header


def _create_test_patient() -> str:
    """테스트용 환자 생성 → patient UUID 반환"""
    r = httpx.post(
        f"{API_V1}/patients/",
        json={"patient_code": f"IMG{uuid.uuid4().hex[:6].upper()}"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201
    return r.json()["id"]


# ════════════════════════════════════════════════════════════
# Level 0 — pgvector 확장 검증
# ════════════════════════════════════════════════════════════

class TestPgvector:
    """
    목적: pgvector 0.8.2 설치 및 벡터 연산 동작 확인
    단계: DB 직접 접근으로 vector 타입 기능 검증
    """

    def test_pgvector_extension_installed(self):
        """pgvector 확장이 mediiot DB에 설치되어 있는지 확인"""
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        async def _check():
            engine = create_async_engine(_async_db_url(), echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT extname, extversion FROM pg_extension WHERE extname='vector'")
                )
                row = result.fetchone()
                await engine.dispose()
                return row

        row = asyncio.run(_check())
        print(f"\n  pgvector: extname={row[0]}, version={row[1]}")
        assert row is not None, "pgvector 확장이 설치되지 않음"
        assert row[0] == "vector"
        print(f"  ✅ pgvector {row[1]} 설치 확인")

    def test_vector_column_exists(self):
        """document_embeddings 테이블에 vector 컬럼이 있는지 확인"""
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        async def _check():
            engine = create_async_engine(_async_db_url(), echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(text("""
                    SELECT column_name, data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'document_embeddings'
                    AND column_name = 'embedding'
                """))
                row = result.fetchone()
                await engine.dispose()
                return row

        row = asyncio.run(_check())
        print(f"\n  embedding 컬럼: {row}")
        assert row is not None, "embedding 컬럼 없음"
        # pgvector의 vector 타입은 udt_name이 'vector'
        assert row[2] == "vector" or row[1] == "USER-DEFINED", (
            f"vector 타입이 아님: {row}"
        )
        print(f"  ✅ vector 컬럼 확인: {row[1]} (udt={row[2]})")

    def test_tables_created(self):
        """Week 3 신규 테이블이 모두 생성되었는지 확인"""
        import asyncio
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        expected = {"eye_images", "medical_documents", "document_embeddings", "diagnosis_embeddings"}

        async def _check():
            engine = create_async_engine(_async_db_url(), echo=False)
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                )
                tables = {row[0] for row in result.fetchall()}
                await engine.dispose()
                return tables

        tables = asyncio.run(_check())
        print(f"\n  현재 테이블: {sorted(tables)}")
        missing = expected - tables
        assert not missing, f"테이블 누락: {missing}"
        print(f"  ✅ Week 3 테이블 모두 확인: {sorted(expected)}")


# ════════════════════════════════════════════════════════════
# Level 1 — 이미지 업로드 API
# ════════════════════════════════════════════════════════════

class TestImageUploadAPI:
    """
    목적: 이미지 업로드 → 메타데이터 저장 → 조회 흐름 검증
    단계: POST /images/upload → GET /images/{id} → GET /images/patient/{patient_id}
    """

    def test_upload_fundus_image(self):
        """
        목적: 안저 사진 업로드 + 메타데이터 저장 확인
        단계: multipart/form-data로 JPEG 업로드 → 201 응답 + 파일 저장 확인
        """
        patient_id = _create_test_patient()
        jpeg_bytes = _make_test_jpeg(size_kb=5)

        print(f"\n  환자 ID: {patient_id[:8]}...")
        print(f"  이미지 크기: {len(jpeg_bytes)} bytes")

        r = httpx.post(
            f"{API_V1}/images/upload",
            files={"file": ("fundus_test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            data={
                "patient_id": patient_id,
                "image_type": "fundus",
                "auto_analyze": "false",
            },
            timeout=TIMEOUT,
        )

        print(f"  POST /images/upload → {r.status_code}")
        body = r.json()
        print(f"  image_id:   {body.get('id', '')[:8]}...")
        print(f"  image_type: {body.get('image_type')}")
        print(f"  file_size:  {body.get('file_size')} bytes")
        print(f"  analyzed:   {body.get('analyzed')}")

        assert r.status_code == 201, f"업로드 실패: {r.text}"
        assert body["patient_id"] == patient_id
        assert body["image_type"] == "fundus"
        assert body["analyzed"] is False
        assert body["file_size"] == len(jpeg_bytes)
        print("  ✅ 안저 이미지 업로드 성공")

        TestImageUploadAPI._image_id   = body["id"]
        TestImageUploadAPI._patient_id = patient_id

    def test_get_image_metadata(self):
        """
        목적: 업로드된 이미지 메타데이터 조회
        단계: GET /images/{id} → 저장 정보 확인
        """
        image_id = getattr(TestImageUploadAPI, "_image_id", None)
        if not image_id:
            pytest.skip("이전 테스트(upload)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/images/{image_id}", timeout=TIMEOUT)
        print(f"\n  GET /images/{image_id[:8]}... → {r.status_code}")
        body = r.json()

        assert r.status_code == 200
        assert body["id"] == image_id
        assert body["image_type"] == "fundus"
        print(f"  ✅ 이미지 메타데이터 조회 성공")

    def test_get_analysis_before_analyze(self):
        """
        목적: 분석 전 분석 결과 조회 → analyzed=False 응답
        단계: GET /images/{id}/analysis → analyzed=False
        """
        image_id = getattr(TestImageUploadAPI, "_image_id", None)
        if not image_id:
            pytest.skip("이전 테스트(upload)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/images/{image_id}/analysis", timeout=TIMEOUT)
        print(f"\n  GET /images/{image_id[:8]}.../analysis → {r.status_code}")
        body = r.json()

        assert r.status_code == 200
        assert body["analyzed"] is False
        assert body["icd10_code"] is None
        print("  ✅ 미분석 상태 확인 (analyzed=False)")

    def test_get_patient_images(self):
        """
        목적: 환자별 이미지 목록 조회
        단계: GET /images/patient/{patient_id} → 방금 업로드한 이미지 포함
        """
        patient_id = getattr(TestImageUploadAPI, "_patient_id", None)
        if not patient_id:
            pytest.skip("이전 테스트(upload)가 실행되지 않았음")

        r = httpx.get(f"{API_V1}/images/patient/{patient_id}", timeout=TIMEOUT)
        print(f"\n  GET /images/patient/{patient_id[:8]}... → {r.status_code}")
        body = r.json()
        print(f"  이미지 수: {len(body)}개")

        assert r.status_code == 200
        assert len(body) >= 1
        assert any(img["image_type"] == "fundus" for img in body)
        print("  ✅ 환자별 이미지 목록 조회 성공")

    def test_upload_unsupported_format_rejected(self):
        """
        목적: 지원하지 않는 파일 형식 거부 확인
        단계: PDF 업로드 → 415 Unsupported Media Type
        """
        patient_id = _create_test_patient()
        r = httpx.post(
            f"{API_V1}/images/upload",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            data={"patient_id": patient_id, "image_type": "fundus"},
            timeout=TIMEOUT,
        )
        print(f"\n  PDF 업로드 시도 → {r.status_code}")
        assert r.status_code == 415
        print("  ✅ 지원하지 않는 파일 형식 거부 확인")

    def test_upload_invalid_image_type_rejected(self):
        """
        목적: 잘못된 image_type 거부 확인
        단계: image_type='xray' → 422
        """
        patient_id = _create_test_patient()
        jpeg_bytes = _make_test_jpeg()
        r = httpx.post(
            f"{API_V1}/images/upload",
            files={"file": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            data={"patient_id": patient_id, "image_type": "xray"},
            timeout=TIMEOUT,
        )
        print(f"\n  잘못된 image_type 시도 → {r.status_code}")
        assert r.status_code == 422
        print("  ✅ 잘못된 image_type 거부 확인")


# ════════════════════════════════════════════════════════════
# Level 2 — VISION 모델 이미지 분석 (실제 LLM 호출)
# ════════════════════════════════════════════════════════════

class TestImageAnalysis:
    """
    목적: 업로드된 이미지에 대한 VISION 모델 분석 검증
    단계: 이미지 업로드 → POST /images/{id}/analyze → 분석 결과 확인

    주의: 실제 LLM 호출 (~30~90초 소요)
    """

    def test_analyze_uploaded_image(self):
        """
        목적: 업로드 이미지 VISION 분석
        단계: 더미 JPEG 업로드 → /analyze 트리거 → 결과 조회
        기대: analyzed=True + condition/icd10_code 채워짐
        """
        # 환자 + 이미지 업로드
        patient_id = _create_test_patient()
        jpeg_bytes = _make_test_jpeg(size_kb=10)

        r_upload = httpx.post(
            f"{API_V1}/images/upload",
            files={"file": ("fundus_analyze.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            data={
                "patient_id": patient_id,
                "image_type": "fundus",
                "auto_analyze": "false",
            },
            timeout=TIMEOUT,
        )
        assert r_upload.status_code == 201
        image_id = r_upload.json()["id"]

        print(f"\n  이미지 업로드: {image_id[:8]}...")
        print(f"  VISION 분석 트리거 중 (30~90초 예상)...")

        # 분석 트리거
        r = httpx.post(f"{API_V1}/images/{image_id}/analyze", timeout=TIMEOUT)
        print(f"  POST /images/{image_id[:8]}.../analyze → {r.status_code}")

        assert r.status_code == 200, f"분석 실패: {r.text}"
        body = r.json()

        print(f"\n  ── 분석 결과 ────────────────────────────────────")
        print(f"  analyzed:    {body.get('analyzed')}")
        print(f"  condition:   {body.get('condition')}")
        print(f"  icd10_code:  {body.get('icd10_code')}")
        print(f"  severity:    {body.get('severity')}")
        print(f"  confidence:  {body.get('confidence')}")
        print(f"  ontology:    {body.get('ontology_passed')}")
        if body.get("raw_analysis"):
            print(f"\n  ── VISION 모델 응답 (앞 300자) ─────────────────")
            print(f"  {body['raw_analysis'][:300]}")

        assert body["analyzed"] is True, "분석이 완료되지 않음"
        assert body["icd10_code"], "ICD 코드 없음"
        print(f"\n  ✅ VISION 이미지 분석 완료: {body['icd10_code']}")

    def test_auto_analyze_on_upload(self):
        """
        목적: 업로드 시 auto_analyze=true로 즉시 분석
        단계: upload 시 auto_analyze=true → analyzed=True 반환
        """
        patient_id = _create_test_patient()
        jpeg_bytes = _make_test_jpeg(size_kb=5)

        print(f"\n  auto_analyze=true 업로드 중...")
        r = httpx.post(
            f"{API_V1}/images/upload",
            files={"file": ("auto_analyze.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")},
            data={
                "patient_id":   patient_id,
                "image_type":   "oct",
                "auto_analyze": "true",
            },
            timeout=TIMEOUT,
        )
        print(f"  POST /images/upload (auto) → {r.status_code}")
        body = r.json()
        print(f"  analyzed: {body.get('analyzed')}")
        print(f"  icd:      {body.get('analysis_icd_code')}")

        assert r.status_code == 201, f"업로드 실패: {r.text}"
        # auto_analyze=true면 업로드 즉시 분석 수행됨
        assert body["analyzed"] is True
        print("  ✅ auto_analyze 업로드 + 즉시 분석 확인")
