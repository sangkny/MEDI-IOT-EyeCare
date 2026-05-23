"""통합 진단 API 스키마 (R4-ML+)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LocationInput(BaseModel):
    lat: float = Field(..., ge=-90, le=90, examples=[37.5665])
    lng: float = Field(..., ge=-180, le=180, examples=[126.9780])


class HospitalRecommendation(BaseModel):
    name: str
    address: str
    distance_km: float
    specialty: str
    phone: str | None = None
    evaluation_score: float = 0.0
    map_url: str | None = None
    urgency: str = "정기 검진"
    data_source: str = "fallback"


class DeviceRecommendation(BaseModel):
    type: Literal["MEDI-EYE-h", "MEDI-EYE-w"]
    device: str
    reason: str
    link: str | None = None
    nutrition: dict[str, str] | None = None


class DiagnosisExplainRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "image_base64": "<base64>",
                "patient_id": "P123456",
                "lang": "ko",
                "location": {"lat": 37.5665, "lng": 126.9780},
            }
        }
    )

    image_base64: str = Field(..., description="안저 JPEG/PNG base64")
    patient_id: str | None = None
    lang: Literal["ko", "en"] = "ko"
    location: LocationInput | None = None
    radius_km: float = Field(default=5.0, ge=1, le=50)


class DiagnosisExplainResponse(BaseModel):
    dr_grade: int = Field(..., ge=0, le=4)
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str
    severity: str
    patient_explanation: str
    clinical_summary: str
    recommended_actions: list[str]
    nearby_hospitals: list[HospitalRecommendation] = Field(default_factory=list)
    ontology_passed: bool
    model_used: str = ""
    decision_mode: str = Field(
        default="legacy",
        description="legacy | four_agent — AGENT_DECISION_MODE",
    )
    audit_trail: dict = Field(
        default_factory=dict,
        description="4-에이전트 결정 감사 추적 (scores, summaries)",
    )


class ComprehensiveDiagnosisRequest(DiagnosisExplainRequest):
    patient_profile: dict[str, str | float | int] | None = Field(
        default=None,
        description="선택: age, has_diabetes, iop_left 등",
    )


class ComprehensiveDiagnosisResponse(DiagnosisExplainResponse):
    device_recommendations: list[DeviceRecommendation] = Field(default_factory=list)
