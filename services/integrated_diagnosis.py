"""통합 진단 오케스트레이션 (CNN + LLM + 병원 + MEDI-EYE)."""
from __future__ import annotations

import base64
import binascii
import logging

from services.device_recommender import DeviceRecommender
from services.explainer import DiagnosisExplainer, DiagnosisExplanation
from services.hospital_recommender import HospitalCandidate, HospitalRecommender
from services.inference_router import predict_dr_from_image_bytes

log = logging.getLogger("services.integrated_diagnosis")


def decode_image_base64(image_base64: str) -> bytes:
    raw = image_base64.strip()
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        return base64.b64decode(raw, validate=False)
    except binascii.Error as exc:
        raise ValueError("invalid image_base64") from exc


async def run_cnn_on_bytes(image_bytes: bytes):
    return await predict_dr_from_image_bytes(image_bytes)


async def run_integrated_explain(
    image_bytes: bytes,
    *,
    patient_lang: str = "ko",
    patient_id: str | None = None,
    location: tuple[float, float] | None = None,
    radius_km: float = 5.0,
    include_devices: bool = False,
    patient_profile: dict | None = None,
) -> tuple[DiagnosisExplanation, list[HospitalCandidate], list]:
    pred = await run_cnn_on_bytes(image_bytes)
    explainer = DiagnosisExplainer()
    explanation = await explainer.explain(
        pred, patient_lang=patient_lang, patient_id=patient_id
    )

    hospitals: list[HospitalCandidate] = []
    if location is not None:
        recommender = HospitalRecommender()
        hospitals = await recommender.recommend(
            explanation.dr_grade, location, radius_km=radius_km
        )

    devices = []
    if include_devices:
        devices = await DeviceRecommender().recommend(
            explanation.dr_grade, patient_profile
        )

    return explanation, hospitals, devices


__all__ = [
    "decode_image_base64",
    "run_integrated_explain",
    "run_cnn_on_bytes",
]
