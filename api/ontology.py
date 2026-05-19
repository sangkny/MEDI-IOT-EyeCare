"""
Ontology 대시보드 통계

GET /api/v1/ontology/stats — 일간 진단 검증 건수·통과율·상위 오류
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.ontology import OntologyStatsResponse
from services.ontology_stats_service import build_medical_ontology_stats

log = logging.getLogger("api.ontology")
router = APIRouter()


@router.get(
    "/stats",
    response_model=OntologyStatsResponse,
    summary="Ontology 일간 통계 (medical)",
)
async def ontology_stats(
    db: AsyncSession = Depends(get_db),
) -> OntologyStatsResponse:
    return await build_medical_ontology_stats(db)
