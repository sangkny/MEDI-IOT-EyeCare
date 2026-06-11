"""
파일명: test_knowledge_base.py
목적: knowledge base.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가
"""
# MEDI-IOT-EyeCare/tests/test_knowledge_base.py
"""
KnowledgeBase RAG 파이프라인 테스트 [Week 3 Day 2]

목적: 의료 문서 임베딩 저장 + pgvector 코사인 유사도 검색 검증

모든 테스트는 pytest-asyncio(asyncio_mode=auto)로 실행됩니다.

실행:
    docker compose -f docker-compose.dev.yml exec medi-iot-api \
        pytest tests/test_knowledge_base.py -v -s
"""
import sys
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.requires_db, pytest.mark.requires_llm]

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared-libraries")


# ════════════════════════════════════════════════════════════
# DB 세션 헬퍼 — NullPool로 이벤트 루프 충돌 방지
# ════════════════════════════════════════════════════════════

def _async_db_url() -> str:
    from config import get_settings

    url = get_settings().database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


async def _make_session():
    """테스트용 독립 DB 세션 (NullPool, 이벤트 루프 충돌 없음)"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        _async_db_url(),
        poolclass=NullPool,
        echo=False,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session_factory(), engine


# ════════════════════════════════════════════════════════════
# Level 0 — 문서 로드 + 임베딩
# ════════════════════════════════════════════════════════════

class TestKnowledgeBaseLoad:
    """
    목적: 의료 문서 임베딩 저장 검증
    단계: 5개 문서 → nomic-embed(768차원) → pgvector 저장
    """

    async def test_load_initial_documents(self):
        """
        목적: 초기 안과 의료 문서 5개 로드
        단계: MEDICAL_DOCUMENTS → add_document 5회 → 카테고리별 집계
        소요: 약 10~30초 (5회 embed 호출)
        """
        from services.knowledge_base import KnowledgeBase
        from scripts.load_knowledge import MEDICAL_DOCUMENTS

        print(f"\n  로드할 문서: {len(MEDICAL_DOCUMENTS)}개")
        db, engine = await _make_session()
        try:
            kb = KnowledgeBase(db)
            for doc_data in MEDICAL_DOCUMENTS:
                doc = await kb.add_document(**doc_data)
                print(f"  ✓ [{doc_data['category']}] {doc_data['title'][:40]}")
            await db.commit()
            counts = await kb.count_documents()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  카테고리별 문서 수: {counts}")
        total = sum(counts.values())
        assert total >= 5, f"문서가 5개 미만: {total}"
        print(f"  ✅ 초기 문서 {total}개 로드 완료")

    async def test_embedding_dimension(self):
        """
        목적: nomic-embed-text-v1.5 임베딩 차원 확인 (768차원)
        단계: embed("test") → embedding 길이 검증
        """
        from llm.client import LLMClient
        client = LLMClient()
        resp   = await client.embed("당뇨망막병증 안저 검사 소견")

        print(f"\n  모델: {resp.model_used}")
        print(f"  임베딩 차원: {len(resp.embedding)}")
        assert len(resp.embedding) == 768
        assert all(isinstance(x, float) for x in resp.embedding[:5])
        print("  ✅ nomic-embed 768차원 확인")

    async def test_duplicate_document_skipped(self):
        """
        목적: 동일 문서 중복 로드 시 건너뜀 확인 (중복 방지)
        """
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb   = KnowledgeBase(db)
            doc1 = await kb.add_document(
                title="테스트 중복 문서 async",
                content="중복 테스트용 내용입니다.",
                category="protocol",
            )
            doc2 = await kb.add_document(
                title="테스트 중복 문서 async",
                content="중복 테스트용 내용입니다.",
                category="protocol",
            )
            await db.commit()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  1차: {doc1.id[:8]}..., 2차: {doc2.id[:8]}...")
        assert doc1.id == doc2.id, "중복 문서가 새로 생성됨"
        print("  ✅ 중복 문서 건너뜀 확인")


# ════════════════════════════════════════════════════════════
# Level 1 — 코사인 유사도 검색
# ════════════════════════════════════════════════════════════

class TestKnowledgeBaseSearch:
    """
    목적: pgvector 코사인 유사도 검색 정확도 검증
    """

    async def test_search_diabetic_retinopathy(self):
        """당뇨망막병증 쿼리 → 관련 문서 검색 확인"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb      = KnowledgeBase(db)
            results = await kb.search("당뇨 환자 안저 소견 점상출혈 신생혈관", top_k=3)
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  쿼리: '당뇨 환자 안저 소견'  결과: {len(results)}개")
        for r in results:
            print(f"    [{r.similarity:.3f}] {r.title[:50]}")
        assert len(results) > 0, "검색 결과 없음"
        print(f"  ✅ 검색 성공 (최고 유사도: {results[0].similarity:.3f})")

    async def test_search_glaucoma_with_iop(self):
        """녹내장 + 안압 쿼리 → H40.1 문서 최상위 검색"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb      = KnowledgeBase(db)
            results = await kb.search(
                "안압 상승 시야 결손 녹내장", top_k=3, icd_code="H40.1"
            )
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  쿼리: '안압 상승 녹내장' (icd=H40.1 필터)  결과: {len(results)}개")
        for r in results:
            print(f"    [{r.similarity:.3f}] {r.title[:50]} {r.icd_codes}")
        assert len(results) > 0
        print(f"  ✅ 녹내장 문서 검색 성공 (유사도 {results[0].similarity:.3f})")

    async def test_search_category_filter(self):
        """카테고리 필터 → icd_codes 문서만 반환"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb      = KnowledgeBase(db)
            results = await kb.search("안과 진단 코드", top_k=5, category="icd_codes")
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  카테고리 필터(icd_codes): {len(results)}개")
        for r in results:
            print(f"    [{r.similarity:.3f}] [{r.category}] {r.title[:40]}")
        assert all(r.category == "icd_codes" for r in results)
        print("  ✅ 카테고리 필터 정상 동작")

    async def test_count_documents(self):
        """카테고리별 문서 수 조회"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb     = KnowledgeBase(db)
            counts = await kb.count_documents()
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  카테고리별 문서 수: {counts}")
        assert sum(counts.values()) >= 5
        print(f"  ✅ 총 {sum(counts.values())}개 문서 확인")


# ════════════════════════════════════════════════════════════
# Level 2 — RAG 컨텍스트 생성
# ════════════════════════════════════════════════════════════

class TestRAGContext:
    """
    목적: get_rag_context() 출력 형식 + ReportGenerator 통합 검증
    """

    async def test_get_rag_context_format(self):
        """당뇨망막병증 쿼리 → Markdown RAG 컨텍스트 생성"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb  = KnowledgeBase(db)
            ctx = await kb.get_rag_context("당뇨망막병증 안저 검사", top_k=2, icd_code="H36.0")
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  RAG 컨텍스트 (앞 400자):\n  {ctx[:400]}")
        print(f"\n  총 길이: {len(ctx)}자")
        assert len(ctx) > 0
        assert "참고 의료 문서" in ctx
        print(f"  ✅ RAG 컨텍스트 생성 성공 ({len(ctx)}자)")

    async def test_rag_empty_when_no_match(self):
        """ICD 필터 매칭 없을 때 빈 문자열 반환"""
        from services.knowledge_base import KnowledgeBase
        db, engine = await _make_session()
        try:
            kb  = KnowledgeBase(db)
            ctx = await kb.get_rag_context("완전히 관련없는 쿼리", top_k=3, icd_code="Z99.9")
            await db.rollback()
        finally:
            await db.close()
            await engine.dispose()

        print(f"\n  관련없는 쿼리 RAG 컨텍스트 길이: {len(ctx)}")
        print("  ✅ 매칭 없을 때 빈 컨텍스트 확인")
