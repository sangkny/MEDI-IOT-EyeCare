"""VISION call 자동 승격 (D R2 Day 4).

EyeImage 의 VISION 분석 결과가 의료 안전 임계값(``confidence >= MEDI_AUTO_PROMOTE_MIN_CONFIDENCE``)
을 통과하면, 분석 직후 자동으로 ``Diagnosis`` 로 승격하고 ``DiagnosisReview``
큐에 ``pending_review`` 로 진입시킨다. 의사가 결정해야만 정식 진단으로 사용되는
워크플로 (의료 안전) 는 그대로 유지하되, 일일이 ``/clinical/diagnoses/promote``
를 클릭하지 않아도 큐가 채워진다.

설계:
    - 자동 promote 의 임계값은 env 로 외부화 — 운영자가 모델 신뢰도에 따라 조정.
    - confidence 가 0.7 미만이거나 ontology_passed=False 면 skip (수동 검토 필요).
    - ``model_used`` 에 ``consensus`` 가 포함된 결과만 자동 promote 후보로 본다
      (FAST/HEAVY 단독은 의사 검토 큐로 명시 승격 필요 — 보수적 안전판).
    - Prometheus 메트릭 ``medi_auto_promote_total{outcome=...}`` 한 줄.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from models.clinical import DiagnosisReview, ReviewStatusEnum
from models.medical import (
    Diagnosis,
    DiagnosisSeverityEnum,
    EyeExam,
    EyeImage,
)


log = logging.getLogger("services.auto_promote")


# ── env 토글 ──────────────────────────────────────────────


def _min_confidence() -> float:
    try:
        return float(os.getenv("MEDI_AUTO_PROMOTE_MIN_CONFIDENCE", "0.70"))
    except ValueError:
        return 0.70


def _enabled() -> bool:
    return os.getenv("MEDI_AUTO_PROMOTE_ENABLED", "1") in {"1", "true", "TRUE"}


def _consensus_required() -> bool:
    return os.getenv("MEDI_AUTO_PROMOTE_CONSENSUS_ONLY", "1") in {"1", "true", "TRUE"}


# ── 메트릭 (best-effort) ─────────────────────────────────


def _emit_metric(outcome: str) -> None:
    """``medi_auto_promote_total{outcome}`` — prometheus 가 없으면 silent."""
    try:
        from prometheus_client import Counter

        global _AUTO_PROMOTE_COUNTER
        try:
            _AUTO_PROMOTE_COUNTER
        except NameError:
            _AUTO_PROMOTE_COUNTER = Counter(
                "medi_auto_promote_total",
                "VISION 자동 승격 결과 카운트",
                ["outcome"],
            )
        _AUTO_PROMOTE_COUNTER.labels(outcome=outcome).inc()
    except Exception:
        pass


# ── 코어 ──────────────────────────────────────────────────


async def try_auto_promote_for_image(
    db: AsyncSession, image: EyeImage
) -> dict[str, Any]:
    """이미지 분석 결과를 보고 자동 승격 가능 여부 판단 + 실행.

    반환:
        ``{"outcome": "...", "diagnosis_id": "...", "review_id": "...", "reason": "..."}``
        outcome: ``skipped_disabled`` | ``skipped_no_analysis`` |
                  ``skipped_low_confidence`` | ``skipped_non_consensus`` |
                  ``skipped_no_exam`` | ``promoted`` | ``failed``
    """
    if not _enabled():
        _emit_metric("skipped_disabled")
        return {"outcome": "skipped_disabled", "reason": "env disabled"}

    if not image.analyzed or not image.analysis_result or not image.analysis_icd_code:
        _emit_metric("skipped_no_analysis")
        return {"outcome": "skipped_no_analysis", "reason": "no analysis"}

    try:
        data = json.loads(image.analysis_result or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}

    conf = 0.0
    try:
        conf = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    min_c = _min_confidence()
    if conf < min_c:
        _emit_metric("skipped_low_confidence")
        return {
            "outcome": "skipped_low_confidence",
            "reason": f"confidence={conf:.2f} < {min_c:.2f}",
        }

    if not bool(data.get("ontology_passed", False)):
        _emit_metric("skipped_low_confidence")
        return {
            "outcome": "skipped_low_confidence",
            "reason": "ontology_passed=False — 수동 검토 필요",
        }

    model_used = str(data.get("model_used") or "").lower()
    if _consensus_required() and "consensus" not in model_used:
        _emit_metric("skipped_non_consensus")
        return {
            "outcome": "skipped_non_consensus",
            "reason": f"model_used={model_used!r} — consensus 가 아닌 결과는 수동 승격 필요",
        }

    if not image.exam_id:
        _emit_metric("skipped_no_exam")
        return {
            "outcome": "skipped_no_exam",
            "reason": "image.exam_id 미설정 — 자동 승격 불가",
        }
    exam = await db.get(EyeExam, image.exam_id)
    if exam is None:
        _emit_metric("skipped_no_exam")
        return {"outcome": "skipped_no_exam", "reason": "linked exam not found"}

    severity = (
        image.analysis_severity
        or data.get("severity")
        or DiagnosisSeverityEnum.MILD.value
    )
    try:
        sev_enum = DiagnosisSeverityEnum(severity)
    except ValueError:
        sev_enum = DiagnosisSeverityEnum.MILD

    diag = Diagnosis(
        id=str(uuid.uuid4()),
        exam_id=image.exam_id,
        diagnosis_code=image.analysis_icd_code,
        diagnosis_name=str(
            data.get("condition_kr") or data.get("condition") or "VISION 분석 진단"
        )[:200],
        severity=sev_enum,
        report=str(
            data.get("brief_summary") or data.get("raw_analysis") or ""
        )[:8000],
        treatment_plan=None,
        llm_model=data.get("model_used"),
        llm_iterations=1,
        ontology_passed=True,
        confidence_score=conf,
    )
    db.add(diag)
    await db.flush()

    review = DiagnosisReview(
        id=str(uuid.uuid4()),
        diagnosis_id=diag.id,
        status=ReviewStatusEnum.PENDING_REVIEW.value,
        review_notes=(
            f"[auto-promoted] confidence={conf:.2f} model={data.get('model_used')!r} "
            f"— 의사 최종 검토 필요"
        ),
    )
    db.add(review)
    await db.flush()

    log.info(
        "auto_promote: image=%s diag=%s review=%s icd=%s severity=%s conf=%.2f",
        image.id[:8], diag.id[:8], review.id[:8],
        diag.diagnosis_code, sev_enum.value, conf,
    )
    _emit_metric("promoted")
    return {
        "outcome": "promoted",
        "diagnosis_id": diag.id,
        "review_id": review.id,
        "reason": f"confidence={conf:.2f} >= {min_c:.2f}, consensus",
    }


__all__ = ["try_auto_promote_for_image"]
