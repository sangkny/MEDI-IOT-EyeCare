"""FHIR R4 최소 export 빌더 (D R3 D4).

Patient · Observation(안저 VISION) · DiagnosticReport(AI 진단) 를
``application/fhir+json`` 로 직렬화한다. PHI face crop / EXIF strip 은 R4+ 백로그.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from models.medical import (
    Diagnosis,
    DiagnosisSeverityEnum,
    EyeExam,
    EyeImage,
    GenderEnum,
    Patient,
)

FHIR_JSON = "application/fhir+json"
MEDI_SYSTEM = "urn:medi:iot:eyecare"
ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10"
LOINC_SYSTEM = "http://loinc.org"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta(*, profile: list[str] | None = None) -> dict[str, Any]:
    m: dict[str, Any] = {"lastUpdated": _now_iso()}
    if profile:
        m["profile"] = profile
    return m


def _gender_fhir(g: GenderEnum | None) -> str | None:
    if g is None:
        return None
    return g.value


def _severity_display(sev: str | DiagnosisSeverityEnum | None) -> str:
    if sev is None:
        return "unknown"
    val = sev.value if isinstance(sev, DiagnosisSeverityEnum) else str(sev)
    return val


def patient_to_fhir(patient: Patient) -> dict[str, Any]:
    """Patient 리소스 — PII 이름은보내지 않음 (patient_code 만 identifier)."""
    resource: dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient.id,
        "meta": _meta(
            profile=["http://hl7.org/fhir/StructureDefinition/Patient"],
        ),
        "identifier": [
            {
                "system": f"{MEDI_SYSTEM}:patient-code",
                "value": patient.patient_code,
            },
        ],
        "active": bool(patient.is_active),
    }
    if patient.date_of_birth:
        resource["birthDate"] = patient.date_of_birth.isoformat()
    g = _gender_fhir(patient.gender)
    if g:
        resource["gender"] = g
    if patient.primary_diagnosis_code:
        resource["extension"] = [
            {
                "url": f"{MEDI_SYSTEM}:StructureDefinition/primary-icd10",
                "valueCodeableConcept": {
                    "coding": [
                        {
                            "system": ICD10_SYSTEM,
                            "code": patient.primary_diagnosis_code,
                        }
                    ],
                },
            }
        ]
    return resource


def observation_from_image(image: EyeImage, patient: Patient) -> dict[str, Any]:
    """EyeImage VISION 분석 → Observation (imaging)."""
    data: dict[str, Any] = {}
    if image.analysis_result:
        try:
            data = json.loads(image.analysis_result)
        except (TypeError, json.JSONDecodeError):
            data = {}

    icd = image.analysis_icd_code or data.get("icd10_code") or "H57.9"
    effective = (
        image.analyzed_at.isoformat()
        if image.analyzed_at
        else image.uploaded_at.isoformat()
    )
    conf = data.get("confidence")
    components: list[dict[str, Any]] = []
    if conf is not None:
        components.append(
            {
                "code": {
                    "coding": [
                        {
                            "system": LOINC_SYSTEM,
                            "code": "LA11837-4",
                            "display": "AI confidence",
                        }
                    ],
                },
                "valueQuantity": {
                    "value": float(conf),
                    "unit": "probability",
                    "system": "http://unitsofmeasure.org",
                    "code": "1",
                },
            }
        )
    if data.get("severity") or image.analysis_severity:
        components.append(
            {
                "code": {
                    "text": "Severity",
                },
                "valueCodeableConcept": {
                    "text": _severity_display(
                        data.get("severity") or image.analysis_severity
                    ),
                },
            }
        )

    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": image.id,
        "meta": _meta(
            profile=["http://hl7.org/fhir/StructureDefinition/Observation"],
        ),
        "status": "final" if image.analyzed else "registered",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "imaging",
                        "display": "Imaging",
                    }
                ],
            }
        ],
        "code": {
            "coding": [
                {
                    "system": LOINC_SYSTEM,
                    "code": "71485-7",
                    "display": "Diabetic retinopathy severity",
                }
            ],
            "text": f"MEDI fundus VISION ({image.image_type.value})",
        },
        "subject": {"reference": f"Patient/{patient.id}"},
        "effectiveDateTime": effective,
        "valueCodeableConcept": {
            "coding": [{"system": ICD10_SYSTEM, "code": icd}],
            "text": data.get("condition_kr") or data.get("condition"),
        },
    }
    if components:
        resource["component"] = components
    if data.get("model_used"):
        resource["device"] = {
            "display": str(data["model_used"])[:200],
        }
    return resource


def diagnostic_report_from_diagnosis(
    diagnosis: Diagnosis,
    exam: EyeExam,
    patient: Patient,
) -> dict[str, Any]:
    """Diagnosis → DiagnosticReport."""
    effective = diagnosis.created_at.isoformat() if diagnosis.created_at else _now_iso()
    resource: dict[str, Any] = {
        "resourceType": "DiagnosticReport",
        "id": diagnosis.id,
        "meta": _meta(
            profile=["http://hl7.org/fhir/StructureDefinition/DiagnosticReport"],
        ),
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                        "code": "RAD",
                        "display": "Radiology",
                    }
                ],
            }
        ],
        "code": {
            "coding": [
                {
                    "system": ICD10_SYSTEM,
                    "code": diagnosis.diagnosis_code,
                    "display": diagnosis.diagnosis_name,
                }
            ],
        },
        "subject": {"reference": f"Patient/{patient.id}"},
        "effectiveDateTime": effective,
        "issued": effective,
        "conclusion": (diagnosis.report or diagnosis.diagnosis_name or "")[:4000],
        "conclusionCode": [
            {
                "coding": [
                    {
                        "system": ICD10_SYSTEM,
                        "code": diagnosis.diagnosis_code,
                    }
                ],
            }
        ],
        "extension": [
            {
                "url": f"{MEDI_SYSTEM}:StructureDefinition/severity",
                "valueCode": _severity_display(diagnosis.severity),
            },
        ],
    }
    if diagnosis.confidence_score is not None:
        resource["extension"].append(
            {
                "url": f"{MEDI_SYSTEM}:StructureDefinition/confidence",
                "valueDecimal": float(diagnosis.confidence_score),
            }
        )
    if diagnosis.llm_model:
        resource["extension"].append(
            {
                "url": f"{MEDI_SYSTEM}:StructureDefinition/llm-model",
                "valueString": diagnosis.llm_model[:200],
            }
        )
    if exam:
        resource["encounter"] = {
            "reference": f"EyeExam/{exam.id}",
            "display": exam.exam_type.value,
        }
    return resource


def patient_bundle(
    patient: Patient,
    *,
    observations: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Patient 중심 minimal Bundle (type=searchset)."""
    entries: list[dict[str, Any]] = [
        {
            "fullUrl": f"urn:uuid:{patient.id}",
            "resource": patient_to_fhir(patient),
        }
    ]
    for obs in observations:
        entries.append(
            {
                "fullUrl": f"urn:uuid:{obs['id']}",
                "resource": obs,
            }
        )
    for rep in reports:
        entries.append(
            {
                "fullUrl": f"urn:uuid:{rep['id']}",
                "resource": rep,
            }
        )
    return {
        "resourceType": "Bundle",
        "id": f"patient-{patient.id}",
        "meta": _meta(),
        "type": "searchset",
        "timestamp": _now_iso(),
        "total": len(entries),
        "entry": entries,
    }


__all__ = [
    "FHIR_JSON",
    "patient_to_fhir",
    "observation_from_image",
    "diagnostic_report_from_diagnosis",
    "patient_bundle",
]
