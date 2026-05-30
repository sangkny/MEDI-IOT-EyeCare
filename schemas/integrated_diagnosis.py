"""통합 진단 API 스키마 (R4-ML+)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GLAUCOMA_GRADE_LABELS = ("normal", "suspect", "glaucoma")
AMD_GRADE_LABELS = ("normal", "early", "intermediate", "advanced")


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


class HotspotRegion(BaseModel):
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    intensity: float = Field(..., ge=0, le=1)
    x_px: int | None = None
    y_px: int | None = None
    region: str = ""
    lesion_type: str = ""


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
    heatmap_base64: str | None = None
    heatmap_width: int | None = None
    heatmap_height: int | None = None
    cam_resolution: str | None = None
    lesion_labels: list[str] = Field(default_factory=list)
    lesion_description: str = ""
    high_risk_regions: list[str] = Field(default_factory=list)
    attention_score: float | None = None
    hotspot_regions: list[HotspotRegion] = Field(default_factory=list)
    gradcam_version: str | None = None
    heatmap_error: str | None = None


class ComprehensiveDiagnosisRequest(DiagnosisExplainRequest):
    patient_profile: dict[str, str | float | int] | None = Field(
        default=None,
        description="선택: age, has_diabetes, iop_left 등",
    )


class DRResult(BaseModel):
    dr_grade: int = Field(..., ge=0, le=4)
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str
    severity: str


class GlaucomaResult(BaseModel):
    glaucoma_grade: int = Field(..., ge=0, le=2, description="0:정상 1:의심 2:확진")
    grade_label: str = Field(..., description="normal/suspect/glaucoma")
    cup_disc_ratio: float | None = Field(default=None, ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str = "H40.1"
    severity: str = Field(default="", description="normal/suspect/glaucoma (alias)")
    referral_urgency: str = Field(
        default="none",
        description="immediate/routine/none",
    )


class AMDResult(BaseModel):
    amd_grade: int = Field(..., ge=0, le=3, description="0:정상 1:초기 2:중기 3:말기")
    grade_label: str = Field(..., description="normal/early/intermediate/advanced")
    drusen_detected: bool
    subtype: str | None = Field(default=None, description="dry/wet/none")
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str = "H35.31"


class MyopiaResult(BaseModel):
    myopia_grade: int = Field(..., ge=0, le=3, description="0:정상 1:경도 2:중등도 3:고도")
    confidence: float = Field(..., ge=0, le=1)
    severity: str


class MultiIndicationResult(BaseModel):
    dr: DRResult | None = None
    glaucoma: GlaucomaResult | None = None
    amd: AMDResult | None = None
    myopia: MyopiaResult | None = None
    active_tasks: list[str] = Field(default_factory=list)
    icd10_codes: dict[str, str] = Field(default_factory=dict)
    primary_finding: str = ""
    referral_urgency: str = Field(default="none", description="immediate/routine/none")
    audit_trail: dict = Field(default_factory=dict)


class ComprehensiveDiagnosisResponse(DiagnosisExplainResponse):
    device_recommendations: list[DeviceRecommendation] = Field(default_factory=list)
    glaucoma_grade: int | None = Field(default=None, ge=0, le=2)
    amd_grade: int | None = Field(default=None, ge=0, le=3)
    myopia_grade: int | None = Field(default=None, ge=0, le=3)
    active_tasks: list[str] = Field(default_factory=list)
    icd10_codes: dict[str, str] = Field(default_factory=dict)
    multi_indication: MultiIndicationResult | None = None
