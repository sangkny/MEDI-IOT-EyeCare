"""AutoNoGaDa / ReportGenerator 연동 — comprehensive 결과 → 환자 보고서."""
from __future__ import annotations

import logging
from datetime import date
from types import SimpleNamespace
from typing import Any

from services.report_gen import ReportGenerator

log = logging.getLogger("services.autonogada_integration")


def format_comprehensive_findings(payload: dict[str, Any]) -> str:
    """comprehensive / lab JSON → ReportGenerator용 소견 텍스트."""
    lines = [
        f"환자 ID: {payload.get('patient_id', 'unknown')}",
        f"눈: {payload.get('eye', 'unknown')}",
    ]
    for key in ("dr", "glaucoma", "amd", "myopia", "screening"):
        block = payload.get(key)
        if block:
            lines.append(f"{key}: {block}")
    if oa := payload.get("overall_assessment"):
        lines.append(f"overall_assessment: {oa}")
    return "\n".join(lines)


def _exam_from_payload(payload: dict[str, Any]) -> SimpleNamespace:
    pid = str(payload.get("patient_id") or "lab")
    eye = str(payload.get("eye") or "unknown")
    return SimpleNamespace(
        id=f"{pid}-{eye}",
        patient_id=pid,
        exam_type="fundus",
        exam_date=date.today(),
        icd_code=payload.get("icd_code"),
        iop_left=payload.get("iop_left"),
        iop_right=payload.get("iop_right"),
        visual_acuity_left=payload.get("visual_acuity_left"),
        visual_acuity_right=payload.get("visual_acuity_right"),
        raw_findings=format_comprehensive_findings(payload),
        ai_summary=payload.get("ai_summary"),
    )


async def generate_fundus_report(
    payload: dict[str, Any],
    *,
    strategy: str = "consensus",
) -> dict[str, Any]:
    """Fundus comprehensive JSON → LLM 진단 보고서 (Orchestrator CONSENSUS)."""
    exam = _exam_from_payload(payload)
    log.info("AutoNoGaDa report | patient=%s eye=%s", exam.patient_id, payload.get("eye"))
    gen = ReportGenerator()
    result = await gen.generate(exam, strategy=strategy, use_rag=False, db=None)
    return {
        "report": result.get("report", ""),
        "model_used": result.get("llm_model"),
        "ontology_passed": result.get("ontology_passed"),
        "latency_ms": result.get("latency_ms"),
        "diagnosis_code": result.get("diagnosis_code"),
        "diagnosis_name": result.get("diagnosis_name"),
        "severity": result.get("severity"),
        "treatment_plan": result.get("treatment_plan"),
    }
