# MEDI-IOT-EyeCare/services/knowledge_base.py
"""
KnowledgeBase — 의료 지식베이스 RAG 서비스 [Week 3 Day 2]

역할:
  1. 안과 의료 문서를 nomic-embed(768차원)로 임베딩하여 pgvector에 저장
  2. 쿼리에 대해 코사인 유사도 검색 → 상위 K개 관련 문서 반환
  3. ReportGenerator에 검색 결과를 컨텍스트로 제공 (RAG 통합)

사용 흐름:
    kb = KnowledgeBase(db_session)

    # 문서 추가
    doc = await kb.add_document(
        title="당뇨망막병증 진단 기준",
        content="비증식성 당뇨망막병증은...",
        category="diagnosis_criteria",
        icd_codes=["H36.0"],
    )

    # 유사 문서 검색
    results = await kb.search("당뇨 환자 안저 소견 해석", top_k=3)
    for r in results:
        print(r.title, r.similarity)
"""
import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from llm.client import LLMClient
from models.knowledge import MedicalDocument, DocumentEmbedding

log = logging.getLogger("services.knowledge_base")

EMBEDDING_DIM = 768


@dataclass
class SearchResult:
    """지식 검색 결과 단건"""
    id:          str
    title:       str
    content:     str
    category:    str
    icd_codes:   list[str]
    similarity:  float        # 코사인 유사도 (0.0~1.0, 높을수록 유사)
    chunk_index: int = 0


class KnowledgeBase:
    """
    의료 지식베이스 — RAG 파이프라인 핵심

    PostgreSQL + pgvector 기반으로 의료 문서를 저장하고
    의미적 유사도 검색(Semantic Search)을 제공합니다.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db     = db
        self._client = LLMClient()
        log.info("KnowledgeBase 초기화 (pgvector + nomic-embed)")

    # ══════════════════════════════════════════════════════
    # 문서 추가
    # ══════════════════════════════════════════════════════

    async def add_document(
        self,
        title:      str,
        content:    str,
        category:   str,
        icd_codes:  list[str] | None = None,
        source:     str | None = None,
        chunk_index: int = 0,
    ) -> MedicalDocument:
        """
        의료 문서를 임베딩하여 지식베이스에 저장

        Args:
            title:       문서 제목
            content:     문서 내용 (전체 텍스트)
            category:    분류 (diagnosis_criteria|treatment|icd_codes|protocol)
            icd_codes:   관련 ICD-10 코드 목록
            source:      출처 (학회 가이드라인 등)
            chunk_index: 긴 문서 청킹 시 순서

        Returns:
            저장된 MedicalDocument
        """
        import uuid

        # 중복 확인 (title + category 동일하면 스킵)
        existing = await self._db.scalar(
            select(MedicalDocument).where(
                MedicalDocument.title    == title,
                MedicalDocument.category == category,
                MedicalDocument.chunk_index == chunk_index,
            )
        )
        if existing:
            log.info(f"[KB] 중복 문서 스킵: {title[:40]}")
            return existing

        # 1. 문서 저장
        doc = MedicalDocument(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            category=category,
            icd_codes=icd_codes or [],
            source=source,
            chunk_index=chunk_index,
        )
        self._db.add(doc)
        await self._db.flush()

        # 2. 임베딩 생성 + 저장
        embed_text = f"{title}\n{content}"
        try:
            embed_resp = await self._client.embed(embed_text)
            embedding  = embed_resp.embedding
            try:
                from services.llm_telemetry import record_embedding_response

                await record_embedding_response(embed_resp, embed_text)
            except Exception:
                pass

            emb = DocumentEmbedding(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                embedding=embedding,
                model_name=embed_resp.model_used or "nomic-embed-text-v1.5",
            )
            self._db.add(emb)
            await self._db.flush()

            log.info(
                f"[KB] 문서 추가: [{category}] {title[:40]} "
                f"(dim={len(embedding)})"
            )
        except Exception as e:
            log.error(f"[KB] 임베딩 실패: {e} — 문서는 텍스트로만 저장")

        return doc

    # ══════════════════════════════════════════════════════
    # 의미적 검색
    # ══════════════════════════════════════════════════════

    async def search(
        self,
        query:    str,
        top_k:    int = 5,
        category: str | None = None,
        icd_code: str | None = None,
    ) -> list[SearchResult]:
        """
        자연어 쿼리로 유사 의료 문서 검색 (코사인 유사도)

        Args:
            query:    검색 쿼리 (자연어)
            top_k:    반환할 최대 문서 수 (기본 5)
            category: 특정 카테고리로 필터링 (선택)
            icd_code: 특정 ICD 코드로 필터링 (선택)

        Returns:
            SearchResult 목록 (유사도 내림차순)
        """
        log.info(f"[KB] 검색: '{query[:50]}' (top_k={top_k})")

        # 쿼리 임베딩
        try:
            embed_resp    = await self._client.embed(query)
            query_vector  = embed_resp.embedding
            try:
                from services.llm_telemetry import record_embedding_response

                await record_embedding_response(embed_resp, query)
            except Exception:
                pass
        except Exception as e:
            log.error(f"[KB] 쿼리 임베딩 실패: {e}")
            return await self._fallback_text_search(query, top_k, category, icd_code)

        # pgvector 코사인 유사도 검색
        # 1 - (embedding <=> query_vector) = 코사인 유사도
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        filters = ["de.embedding IS NOT NULL"]
        if category:
            filters.append(f"d.category = '{category}'")
        if icd_code:
            filters.append(f"d.icd_codes::text LIKE '%{icd_code}%'")

        where_clause = " AND ".join(filters)

        sql = text(f"""
            SELECT
                d.id, d.title, d.content, d.category,
                d.icd_codes, d.chunk_index,
                1 - (de.embedding <=> '{vector_str}'::vector) AS similarity
            FROM medical_documents d
            JOIN document_embeddings de ON de.document_id = d.id
            WHERE d.is_active = true AND {where_clause}
            ORDER BY de.embedding <=> '{vector_str}'::vector
            LIMIT :top_k
        """)

        try:
            result = await self._db.execute(sql, {"top_k": top_k})
            rows   = result.fetchall()
        except Exception as e:
            log.error(f"[KB] pgvector 검색 실패: {e}")
            return await self._fallback_text_search(query, top_k, category, icd_code)

        results = []
        for row in rows:
            icd = row[4] if isinstance(row[4], list) else (
                json.loads(row[4]) if row[4] else []
            )
            results.append(SearchResult(
                id=row[0], title=row[1], content=row[2],
                category=row[3], icd_codes=icd,
                chunk_index=row[5], similarity=float(row[6]),
            ))

        log.info(f"[KB] 검색 완료: {len(results)}개 결과")
        return results

    async def _fallback_text_search(
        self,
        query:    str,
        top_k:    int,
        category: str | None,
        icd_code: str | None,
    ) -> list[SearchResult]:
        """pgvector 실패 시 텍스트 LIKE 검색으로 대체"""
        log.warning("[KB] pgvector fallback: 텍스트 검색 사용")
        q = select(MedicalDocument).where(MedicalDocument.is_active == True)  # noqa: E712

        if category:
            q = q.where(MedicalDocument.category == category)

        docs = (await self._db.scalars(q.limit(top_k * 2))).all()

        # 간단한 키워드 매칭
        keywords = query.lower().split()
        scored   = []
        for doc in docs:
            text_lower = (doc.title + doc.content).lower()
            score = sum(1 for kw in keywords if kw in text_lower) / max(len(keywords), 1)
            if score > 0:
                scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            SearchResult(
                id=d.id, title=d.title, content=d.content,
                category=d.category,
                icd_codes=d.icd_codes or [],
                chunk_index=d.chunk_index,
                similarity=s,
            )
            for d, s in scored[:top_k]
        ]

    # ══════════════════════════════════════════════════════
    # RAG 컨텍스트 생성
    # ══════════════════════════════════════════════════════

    async def get_rag_context(
        self,
        query:    str,
        top_k:    int = 3,
        icd_code: str | None = None,
    ) -> str:
        """
        진단 보고서 생성 시 RAG 컨텍스트 문자열 반환

        Orchestrator에게 전달할 참고 문헌 형식으로 포맷팅합니다.

        Returns:
            "## 참고 의료 문서\n\n**[제목]**\n내용...\n\n..." 형식 문자열
        """
        results = await self.search(query, top_k=top_k, icd_code=icd_code)
        if not results:
            return ""

        lines = ["## 참고 의료 문서 (RAG)\n"]
        for i, r in enumerate(results, 1):
            lines += [
                f"### {i}. {r.title}",
                f"*(유사도: {r.similarity:.2f}, 카테고리: {r.category})*",
                "",
                r.content[:500] + ("..." if len(r.content) > 500 else ""),
                "",
            ]

        context = "\n".join(lines)
        log.info(
            f"[KB] RAG 컨텍스트 생성: {len(results)}개 문서, "
            f"{len(context)}자"
        )
        return context

    # ══════════════════════════════════════════════════════
    # 유틸리티
    # ══════════════════════════════════════════════════════

    async def count_documents(self) -> dict[str, int]:
        """카테고리별 문서 수 반환"""
        result = await self._db.execute(
            text("""
                SELECT category, COUNT(*) as cnt
                FROM medical_documents
                WHERE is_active = true
                GROUP BY category
                ORDER BY cnt DESC
            """)
        )
        return {row[0]: row[1] for row in result.fetchall()}

    async def get_document_by_id(self, doc_id: str) -> MedicalDocument | None:
        """문서 단건 조회"""
        return await self._db.scalar(
            select(MedicalDocument).where(MedicalDocument.id == doc_id)
        )
