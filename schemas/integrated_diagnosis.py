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


class CupDiscRatioDetail(BaseModel):
    value: float = Field(..., ge=0, le=1)
    category: Literal["normal", "suspect", "glaucoma"]
    method: str = Field(..., description="probability_based | segmentation_based")
    confidence_interval: list[float] = Field(
        default_factory=list,
        description="[low, high] 신뢰구간",
    )
    clinical_note: str = ""


class GlaucomaLesionAnnotation(BaseModel):
    type: str
    confidence: float = Field(..., ge=0, le=1)
    region: str = ""


class GlaucomaHeatmap(BaseModel):
    image_base64: str = ""
    resolution: str = "original"
    lesion_annotations: list[GlaucomaLesionAnnotation] = Field(default_factory=list)
    hotspot_regions: list[str] = Field(default_factory=list)
    gradcam_version: str | None = None
    heatmap_error: str | None = None


class GlaucomaResult(BaseModel):
    glaucoma_grade: int = Field(..., ge=0, le=2, description="0:정상 1:의심 2:확진")
    grade_label: str = Field(..., description="normal/suspect/glaucoma")
    label: str = Field(..., description="normal | glaucoma (이진)")
    probability: float = Field(..., ge=0, le=1, description="glaucoma 양성 확률 (sigmoid)")
    risk_level: Literal["LOW", "MODERATE", "HIGH"] = Field(
        ...,
        description="LOW(<0.3) / MODERATE(0.3~0.7) / HIGH(>0.7)",
    )
    cup_disc_ratio: CupDiscRatioDetail | None = None
    heatmap: GlaucomaHeatmap | None = None
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str = "H40.1"
    severity: str = Field(default="", description="normal/suspect/glaucoma (alias)")
    referral_urgency: str = Field(
        default="none",
        description="immediate/routine/none",
    )
    model_used: str = Field(default="", description="예: cnn(efficientnet_b4_glaucoma)")
    decision_mode: str = Field(
        default="legacy",
        description="legacy | four_agent | gate",
    )
    ontology_passed: bool = Field(
        default=True,
        description="Glaucoma SEMANTIC ontology 통과 여부 (GLAU-SEM 룰)",
    )
    decision: str | None = Field(
        default=None,
        description="APPROVE | REVISE | REJECT (audit_trail.decision)",
    )
    audit_trail: dict = Field(default_factory=dict)


class AMDLesionAnnotation(BaseModel):
    type: str
    confidence: float = Field(..., ge=0, le=1)
    region: str = ""


class AMDHeatmap(BaseModel):
    image_base64: str = ""
    resolution: str = "original"
    lesion_annotations: list[AMDLesionAnnotation] = Field(default_factory=list)
    hotspot_regions: list[str] = Field(default_factory=list)
    gradcam_version: str | None = None
    heatmap_error: str | None = None


class AMDResult(BaseModel):
    amd_grade: int = Field(..., ge=0, le=3, description="0:정상 1:초기 2:중기 3:말기")
    grade_label: str = Field(..., description="normal/early/intermediate/advanced")
    label: str = Field(default="normal", description="normal | amd (이진)")
    probability: float = Field(default=0.0, ge=0, le=1, description="AMD 양성 확률")
    risk_level: Literal["LOW", "MODERATE", "HIGH"] = Field(default="LOW")
    drusen_detected: bool = False
    drusen_type: str | None = Field(
        default=None,
        description="soft/hard/none — drusen 소견 유형",
    )
    subtype: str | None = Field(default=None, description="dry/wet/none (legacy alias)")
    vision_impact: str | None = Field(
        default=None,
        description="minimal/moderate/severe",
    )
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str = "H35.31"
    severity: str = Field(default="", description="normal/early/intermediate/advanced")
    referral_urgency: str = Field(
        default="none",
        description="none/routine/urgent/immediate",
    )
    heatmap: AMDHeatmap | None = None
    model_used: str = Field(default="", description="예: cnn(efficientnet_b4_amd)")
    decision_mode: str = Field(
        default="legacy",
        description="legacy | four_agent | gate",
    )
    ontology_passed: bool = Field(
        default=True,
        description="AMD SEMANTIC ontology 통과 여부 (AMD-SEM 룰)",
    )
    decision: str | None = Field(
        default=None,
        description="APPROVE | REVISE | REJECT (audit_trail.decision)",
    )
    audit_trail: dict = Field(default_factory=dict)


class MyopiaResult(BaseModel):
    myopia_grade: int = Field(..., ge=0, le=3, description="0:정상 1:경도 2:중등도 3:고도")
    probability: float = Field(default=0.0, ge=0, le=1)
    axial_length_estimate: float | None = Field(
        default=None,
        description="추정 안축장(mm) — Phase 3 모델",
    )
    risk_level: Literal["LOW", "MODERATE", "HIGH"] = Field(default="LOW")
    pathological: bool = Field(default=False, description="병적 근시 여부")
    confidence: float = Field(..., ge=0, le=1)
    severity: str = ""


class ScreeningResult(BaseModel):
    """전체 안과 스크리닝 (DR+Glaucoma+AMD+근시 등) — Phase 4+."""

    findings: list[str] = Field(default_factory=list)
    urgent_referral: bool = False
    priority_diseases: list[str] = Field(
        default_factory=list,
        description="우선 의뢰 질환 (glaucoma, dr, amd, myopia, ...)",
    )
    referral_urgency: str = Field(default="none", description="none/routine/immediate")
    model_used: str = ""


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


class DRComprehensiveSummary(BaseModel):
    grade: int = Field(..., ge=0, le=4, alias="dr_grade")
    confidence: float = Field(..., ge=0, le=1)
    icd10_code: str = ""
    severity: str = ""
    decision: str | None = None
    ontology_passed: bool = False
    decision_mode: str = "legacy"
    model_used: str = ""
    audit_trail: dict = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class OverallAssessment(BaseModel):
    referral_urgency: str = Field(
        default="none",
        description="none | routine | immediate | urgent",
    )
    primary_concern: str = Field(
        default="none",
        description="glaucoma | diabetic_retinopathy | amd | none",
    )
    findings: list[str] = Field(default_factory=list)
    recommendation: str = ""


class ComprehensiveFundusResponse(BaseModel):
    """DR + Glaucoma + AMD 통합 Lab 응답."""

    dr: DRComprehensiveSummary
    glaucoma: GlaucomaResult | None = None
    amd: AMDResult | None = None
    heatmap: dict = Field(
        default_factory=dict,
        description='{"dr": {...}, "glaucoma": {...}, "amd": {...}}',
    )
    overall_assessment: OverallAssessment
    active_tasks: list[str] = Field(default_factory=list)
    input_format: str | None = None
    nearby_hospitals: list[HospitalRecommendation] = Field(default_factory=list)
    device_recommendations: list[DeviceRecommendation] = Field(default_factory=list)


class ComprehensiveDiagnosisResponse(DiagnosisExplainResponse):
    device_recommendations: list[DeviceRecommendation] = Field(default_factory=list)
    glaucoma_grade: int | None = Field(default=None, ge=0, le=2)
    amd_grade: int | None = Field(default=None, ge=0, le=3)
    myopia_grade: int | None = Field(default=None, ge=0, le=3)
    active_tasks: list[str] = Field(default_factory=list)
    icd10_codes: dict[str, str] = Field(default_factory=dict)
    multi_indication: MultiIndicationResult | None = None
