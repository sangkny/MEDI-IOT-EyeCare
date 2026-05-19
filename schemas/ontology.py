"""대시보드용 Ontology 통계 응답."""
from __future__ import annotations

from pydantic import BaseModel, Field


class OntologyErrorBucket(BaseModel):
    code: str = Field(description="오류 코드 또는 요약 라벨")
    count: int = Field(ge=0)
    message: str = ""


class OntologyDomainSlice(BaseModel):
    domain: str
    today_validations: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    top_errors: list[OntologyErrorBucket] = Field(default_factory=list)


class OntologyStatsResponse(BaseModel):
    domain: str = Field(default="medical")
    today_validations: int = Field(ge=0)
    pass_rate: float = Field(ge=0, le=1)
    top_errors: list[OntologyErrorBucket]
    generated_at: str = ""
    service: str = Field(default="medi-iot")
    domains_detail: list[OntologyDomainSlice] = Field(
        default_factory=list,
        description="도메인별 슬라이스 (OntologyMonitor용)",
    )
