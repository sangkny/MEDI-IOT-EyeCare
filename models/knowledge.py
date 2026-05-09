# MEDI-IOT-EyeCare/models/knowledge.py
"""
의료 지식베이스 + 벡터 임베딩 모델 [Week 3 신규]

MedicalDocument:   안과 의료 문서 (진단 기준, 치료 가이드라인 등)
DocumentEmbedding: 문서 벡터 임베딩 (nomic-embed-text-v1.5, 768차원)
DiagnosisEmbedding: 검증된 진단 보고서 임베딩 (RAG 학습용)

pgvector 확장 필요:
    docker compose exec postgres psql -U dev -c "CREATE EXTENSION vector;"
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float,
    ForeignKey, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    # pgvector 패키지 미설치 시 fallback (Text로 대체)
    Vector = None
    PGVECTOR_AVAILABLE = False

from database import Base

EMBEDDING_DIM = 768   # nomic-embed-text-v1.5 차원


class MedicalDocument(Base):
    """
    안과 의료 문서 저장소

    RAG(Retrieval-Augmented Generation) 파이프라인의 지식베이스.
    당뇨망막병증 진단 기준, ICD-10 코드 목록, 치료 가이드라인 등.
    """
    __tablename__ = "medical_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    title: Mapped[str] = mapped_column(
        String(300), nullable=False,
        comment="문서 제목",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="문서 전체 내용",
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="카테고리: diagnosis_criteria|treatment|icd_codes|protocol",
    )
    icd_codes: Mapped[list | None] = mapped_column(
        JSON, nullable=True,
        comment="관련 ICD-10 코드 목록 (예: ['H36.0', 'H40.1'])",
    )
    source: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="출처 (대한안과학회 가이드라인 등)",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    chunk_index: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="긴 문서를 청크로 나눈 경우 순서",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 관계
    embedding: Mapped["DocumentEmbedding | None"] = relationship(
        back_populates="document", uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MedicalDocument [{self.category}] {self.title[:40]}>"


class DocumentEmbedding(Base):
    """
    의료 문서 벡터 임베딩

    nomic-embed-text-v1.5 모델(768차원)으로 생성된 임베딩을 저장합니다.
    pgvector의 벡터 검색으로 유사 문서를 빠르게 찾습니다.
    """
    __tablename__ = "document_embeddings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("medical_documents.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # pgvector Vector 타입 (미설치 시 Text fallback)
    embedding: Mapped[str] = mapped_column(
        Vector(EMBEDDING_DIM) if PGVECTOR_AVAILABLE and Vector else Text,
        nullable=False,
        comment=f"벡터 임베딩 ({EMBEDDING_DIM}차원, nomic-embed-text-v1.5)",
    )
    model_name: Mapped[str] = mapped_column(
        String(100), default="text-embedding-nomic-embed-text-v1.5",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    # 관계
    document: Mapped["MedicalDocument"] = relationship(back_populates="embedding")

    def __repr__(self) -> str:
        return f"<DocumentEmbedding doc={self.document_id[:8]}>"


class DiagnosisEmbedding(Base):
    """
    검증된 AI 진단 보고서 임베딩 (RAG 학습용)

    ontology_passed=True인 진단 보고서를 임베딩하여
    새 진단 시 유사 케이스를 참고 자료로 활용합니다.
    """
    __tablename__ = "diagnosis_embeddings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    diagnosis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnoses.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    diagnosis_code: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True,
        comment="ICD-10 코드 (필터링용)",
    )
    embedding: Mapped[str] = mapped_column(
        Vector(EMBEDDING_DIM) if PGVECTOR_AVAILABLE and Vector else Text,
        nullable=False,
    )
    similarity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="검색 시 유사도 점수 (임시 저장용)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<DiagnosisEmbedding [{self.diagnosis_code}]>"
