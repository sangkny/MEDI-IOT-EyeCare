"""SaMD 파트너 인증·과금·FHIR/HL7 포맷."""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.partner import PartnerAccount, PartnerAnalysis, PartnerPlanEnum
from services.integrated_diagnosis import decode_image_base64, run_integrated_explain
from services.retinal_cnn import DR_GRADE_CONDITION


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"medi_{secrets.token_urlsafe(32)}"


async def register_partner(
    db: AsyncSession,
    *,
    partner_id: str,
    name: str,
    plan: str = PartnerPlanEnum.TRIAL.value,
    cost_per_analysis: float = 0.05,
) -> tuple[PartnerAccount, str]:
    existing = await db.scalar(
        select(PartnerAccount).where(PartnerAccount.partner_id == partner_id)
    )
    if existing:
        raise ValueError(f"partner_id already exists: {partner_id}")

    api_key = generate_api_key()
    account = PartnerAccount(
        id=str(uuid.uuid4()),
        partner_id=partner_id.strip(),
        name=name.strip(),
        api_key_hash=hash_api_key(api_key),
        plan=plan,
        cost_per_analysis=cost_per_analysis,
    )
    db.add(account)
    await db.flush()
    return account, api_key


async def authenticate_partner(
    db: AsyncSession,
    *,
    partner_id: str,
    api_key: str,
) -> PartnerAccount:
    key_hash = hash_api_key(api_key)
    account = await db.scalar(
        select(PartnerAccount).where(
            PartnerAccount.partner_id == partner_id.strip(),
            PartnerAccount.api_key_hash == key_hash,
            PartnerAccount.is_active.is_(True),
        )
    )
    if not account:
        raise PermissionError("invalid partner_id or api_key")
    return account


def _grade_label(dr_grade: int) -> str:
    return DR_GRADE_CONDITION.get(dr_grade, ("unknown", "미상"))[1]


def build_fhir_bundle(explanation, *, analysis_id: str, partner_id: str) -> dict[str, Any]:
    cond_kr = _grade_label(explanation.dr_grade)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry": [
            {
                "resource": {
                    "resourceType": "DiagnosticReport",
                    "id": analysis_id,
                    "status": "final",
                    "code": {
                        "coding": [
                            {
                                "system": "http://hl7.org/fhir/sid/icd-10",
                                "code": explanation.icd10_code,
                            }
                        ],
                        "text": cond_kr,
                    },
                    "conclusion": explanation.clinical_summary,
                    "extension": [
                        {
                            "url": "https://medi-iot.local/StructureDefinition/dr-grade",
                            "valueInteger": explanation.dr_grade,
                        },
                        {
                            "url": "https://medi-iot.local/StructureDefinition/confidence",
                            "valueDecimal": round(explanation.confidence, 4),
                        },
                        {
                            "url": "https://medi-iot.local/StructureDefinition/partner-id",
                            "valueString": partner_id,
                        },
                    ],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "Patient explanation"},
                    "valueString": explanation.patient_explanation,
                }
            },
        ],
    }


def build_hl7_oru(explanation, *, analysis_id: str, partner_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icd = explanation.icd10_code or ""
    conf = f"{explanation.confidence:.4f}"
    grade = str(explanation.dr_grade)
    pid = partner_id[:20]
    return (
        f"MSH|^~\\&|MEDI-IOT|PARTNER|EMR|{pid}|{ts}||ORU^R01|{analysis_id}|P|2.5\r"
        f"PID|1||{pid}^^^MEDI||UNKNOWN\r"
        f"OBR|1|||DR-FUNDUS^Fundus DR|||{ts}\r"
        f"OBX|1|NM|DR-GRADE^DR Grade||{grade}|||N|||F\r"
        f"OBX|2|NM|CONF^Confidence||{conf}|||N|||F\r"
        f"OBX|3|ST|ICD10^ICD-10||{icd}|||N|||F\r"
        f"OBX|4|TX|PT-EXPL^Patient Explanation||{explanation.patient_explanation[:200]}|||N|||F\r"
    )


async def run_partner_analyze(
    db: AsyncSession,
    account: PartnerAccount,
    *,
    image_base64: str,
    analysis_type: str = "fundus",
    return_format: str = "json",
    lang: str = "ko",
    patient_id: str | None = None,
    include_heatmap: bool = False,
) -> dict[str, Any]:
    if analysis_type != "fundus":
        raise ValueError("only fundus analysis_type is supported in smoke v1")

    image_bytes = decode_image_base64(image_base64)
    explanation, hospitals, _ = await run_integrated_explain(
        image_bytes,
        patient_lang=lang,
        patient_id=patient_id,
        location=None,
        include_devices=False,
    )

    from services.diagnosis_pipeline import apply_four_agent_decision

    ontology_passed, audit_trail, decision_mode = await apply_four_agent_decision(
        dr_grade=explanation.dr_grade,
        confidence=explanation.confidence,
        icd10_code=explanation.icd10_code,
        patient_explanation=explanation.patient_explanation,
        clinical_summary=explanation.clinical_summary,
        ontology_passed_legacy=explanation.ontology_passed,
        patient_id=patient_id or account.partner_id,
    )

    analysis_id = str(uuid.uuid4())
    cost = float(account.cost_per_analysis)

    payload: dict[str, Any] = {
        "analysis_id": analysis_id,
        "partner_id": account.partner_id,
        "analysis_type": analysis_type,
        "dr_grade": explanation.dr_grade,
        "confidence": explanation.confidence,
        "icd10_code": explanation.icd10_code,
        "severity": explanation.severity,
        "patient_explanation": explanation.patient_explanation,
        "clinical_summary": explanation.clinical_summary,
        "recommended_actions": explanation.recommended_actions,
        "ontology_passed": ontology_passed,
        "model_used": explanation.model_used,
        "decision_mode": decision_mode,
        "audit_trail": audit_trail,
        "cost": cost,
        "currency": "USD",
    }

    heatmap_b64: str | None = None
    if include_heatmap:
        try:
            from services.gradcam import GradCAMVisualizer

            heatmap_b64 = await GradCAMVisualizer().generate_heatmap(image_bytes)
            payload["heatmap_base64"] = heatmap_b64
        except Exception as exc:
            payload["heatmap_error"] = str(exc)[:120]

    fmt = (return_format or "json").strip().lower()
    if fmt == "fhir":
        bundle = build_fhir_bundle(
            explanation, analysis_id=analysis_id, partner_id=account.partner_id
        )
        payload["fhir"] = bundle
        payload["fhir_bundle"] = bundle
    elif fmt == "hl7":
        payload["hl7"] = build_hl7_oru(
            explanation, analysis_id=analysis_id, partner_id=account.partner_id
        )

    record = PartnerAnalysis(
        id=analysis_id,
        partner_account_id=account.id,
        analysis_type=analysis_type,
        return_format=fmt,
        dr_grade=explanation.dr_grade,
        confidence=explanation.confidence,
        icd10_code=explanation.icd10_code,
        severity=explanation.severity,
        result_json=json.dumps(payload, ensure_ascii=False),
        cost=cost,
    )
    db.add(record)
    await db.flush()
    return payload


async def partner_dashboard(
    db: AsyncSession,
    account: PartnerAccount,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_q = await db.scalar(
        select(func.count()).select_from(PartnerAnalysis).where(
            PartnerAnalysis.partner_account_id == account.id
        )
    )
    today_q = await db.scalar(
        select(func.count()).select_from(PartnerAnalysis).where(
            PartnerAnalysis.partner_account_id == account.id,
            PartnerAnalysis.created_at >= day_start,
        )
    )
    avg_conf = await db.scalar(
        select(func.avg(PartnerAnalysis.confidence)).where(
            PartnerAnalysis.partner_account_id == account.id
        )
    )
    total_cost = await db.scalar(
        select(func.sum(PartnerAnalysis.cost)).where(
            PartnerAnalysis.partner_account_id == account.id
        )
    )

    rows = await db.execute(
        select(PartnerAnalysis.dr_grade, func.count())
        .where(PartnerAnalysis.partner_account_id == account.id)
        .group_by(PartnerAnalysis.dr_grade)
    )
    grade_dist = {str(g if g is not None else "na"): c for g, c in rows.all()}

    return {
        "partner_id": account.partner_id,
        "name": account.name,
        "plan": account.plan,
        "analyses_today": int(today_q or 0),
        "analyses_total": int(total_q or 0),
        "avg_confidence": round(float(avg_conf or 0.0), 4),
        "dr_grade_distribution": grade_dist,
        "total_cost_usd": round(float(total_cost or 0.0), 4),
        "cost_per_analysis_usd": account.cost_per_analysis,
    }
