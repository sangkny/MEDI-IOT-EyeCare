"""통합 진단 서비스 단위 테스트 (R4-ML+, Mock 0)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from services.device_recommender import DeviceRecommender
from services.explainer import DiagnosisExplainer
from services.hospital_recommender import HospitalRecommender, _specialty_for_grade
from services.integrated_diagnosis import decode_image_base64
from services.retinal_cnn import DrPrediction, dr_prediction_from_logits


def test_decode_image_base64() -> None:
    import base64

    raw = base64.b64encode(b"fake-image").decode()
    assert decode_image_base64(raw) == b"fake-image"


def test_recommended_actions_by_grade() -> None:
    explainer = DiagnosisExplainer.__new__(DiagnosisExplainer)
    assert len(explainer._get_actions(0, "ko")) >= 2
    assert "즉시" in " ".join(explainer._get_actions(4, "ko"))


def test_specialty_for_grade() -> None:
    sp, urg = _specialty_for_grade(3)
    assert "망막" in sp
    assert urg == "즉시"


@pytest.mark.asyncio
async def test_hospital_recommender_fallback() -> None:
    rec = HospitalRecommender()
    hospitals = await rec.recommend(2, (37.5665, 126.9780), radius_km=10)
    assert len(hospitals) >= 1
    assert hospitals[0].data_source == "fallback"


@pytest.mark.asyncio
async def test_device_recommender_dr2() -> None:
    dev = DeviceRecommender()
    items = await dev.recommend(2, {"has_diabetes": True})
    types = {d.type for d in items}
    assert "MEDI-EYE-h" in types
    assert "MEDI-EYE-w" in types


def test_dr_prediction_grade2() -> None:
    pred = dr_prediction_from_logits([0.1, 0.1, 2.0, 0.1, 0.1])
    assert pred.dr_grade == 2
    assert pred.icd10_code == "H36.0"
