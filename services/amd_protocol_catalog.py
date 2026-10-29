"""MEDI-AMD-001 DRAFT eCRF catalog. Source-supported fields only. No fabricated questionnaires."""
from __future__ import annotations

from services.protocol_ecrf import _field, register_form_catalog

STUDY_ID = "MEDI-AMD-001"
PROTOCOL_VERSION = "0.1"
SOURCE_SHA256 = "85B946928FFCC33FAF1C858D8BC745186BAE3298B737B8B11AED9A3EC54330F5"

# Schedule mapping from DRAFT protocol tables/text. Visit6 referenced in procedures.
VISITS = {
    "V1": "Screening",
    "V2": "Baseline",
    "V3": "EOT ~5w",
    "V4": "Follow-up",
    "V5": "Follow-up ~9w",
    "V6": "End of Study ~21w (procedure-referenced; schedule conflict under review)",
}

REVIEW_FINDINGS = (
    "AMD-WAVE",
    "AMD-SCHED-V6",
    "AMD-EP-VISIT",
    "AMD-N15-N16",
    "AMD-DATA-RETENTION",
    "AMD-DESIGN-RAND",
    "AMD-TX-SETTINGS",
)


def _amd_catalog(version: str) -> tuple[list[dict], list[dict]]:
    if version != PROTOCOL_VERSION:
        # Still emit DRAFT proposal keyed by registered version label.
        pass
    all_visits = ["V1", "V2", "V3", "V4", "V5", "V6"]
    treat_visits = ["V2", "V3"]
    endpoint_visits = ["V2", "V3", "V5", "V6"]
    fields = [
        _field(logical_field_id="SUBJID", form_code="SCREENING", code="SUBJID", unit="code", value_kind="text", visits=["V1"], section="11.2 / screening", protocol_version=version),
        _field(logical_field_id="ICF_DATE", form_code="CONSENT", code="ICF_DATE", unit="date", value_kind="date", visits=["V1"], section="consent", protocol_version=version),
        _field(logical_field_id="ELIG_INCL", form_code="ELIGIBILITY", code="ELIG_INCL", unit="flag", value_kind="text", visits=["V1"], section="inclusion", protocol_version=version, note="criteria text not reproduced"),
        _field(logical_field_id="ELIG_EXCL", form_code="ELIGIBILITY", code="ELIG_EXCL", unit="flag", value_kind="text", visits=["V1"], section="exclusion", protocol_version=version, note="criteria text not reproduced"),
        _field(logical_field_id="AGE", form_code="DEMOG", code="AGE", unit="y", visits=["V1"], section="demographics", protocol_version=version),
        _field(logical_field_id="SEX", form_code="DEMOG", code="SEX", unit="code", value_kind="text", visits=["V1"], section="demographics", protocol_version=version),
        _field(logical_field_id="MH_TERM", form_code="MH", code="MH_TERM", unit="text", value_kind="text", visits=["V1"], section="medical history", protocol_version=version, enforced=False),
        _field(logical_field_id="CM_TERM", form_code="CM", code="CM_TERM", unit="text", value_kind="text", visits=all_visits, section="concomitant meds", protocol_version=version, enforced=False),
        _field(logical_field_id="STUDY_EYE", form_code="STUDY_EYE", code="STUDY_EYE", unit="OD_OS", value_kind="text", visits=["V1", "V2"], section="study eye", protocol_version=version),
        _field(logical_field_id="BCVA-STUDY", form_code="BCVA", code="BCVA", laterality="STUDY", unit="ETDRS_letters", visits=endpoint_visits, section="BCVA primary/secondary", protocol_version=version),
        _field(logical_field_id="DRUSEN-VOL", form_code="OCT_DRUSEN", code="DRUSEN_VOL", laterality="STUDY", unit="mm3", visits=endpoint_visits, section="OCT drusen volume", protocol_version=version),
        _field(logical_field_id="DRUSEN-THK", form_code="OCT_DRUSEN", code="DRUSEN_THK", laterality="STUDY", unit="um", visits=endpoint_visits, section="OCT drusen thickness", protocol_version=version),
        _field(logical_field_id="IOP-REPEAT", form_code="IOP", code="IOP", laterality="STUDY", unit="mmHg", repeated=True, repeat_count=3, visits=all_visits, section="IOP", protocol_version=version),
        _field(logical_field_id="FUNDUS", form_code="IMAGING", code="FUNDUS", laterality="STUDY", unit="performed", value_kind="text", visits=endpoint_visits, section="fundus", protocol_version=version),
        _field(logical_field_id="WIDE_FAF", form_code="IMAGING", code="WIDE_FAF", laterality="STUDY", unit="performed", value_kind="text", visits=endpoint_visits, section="wide FAF", protocol_version=version),
        _field(logical_field_id="SLIT_LAMP", form_code="IMAGING", code="SLIT_LAMP", laterality="STUDY", unit="performed", value_kind="text", visits=all_visits, section="slit-lamp", protocol_version=version),
        _field(logical_field_id="VF", form_code="IMAGING", code="VF", laterality="STUDY", unit="performed", value_kind="text", visits=endpoint_visits, section="visual field", protocol_version=version),
        _field(logical_field_id="TX_DEVICE", form_code="EXPOSURE", code="TX_DEVICE", unit="code", value_kind="text", visits=treat_visits, section="MEDI-EYE exposure", protocol_version=version),
        _field(
            logical_field_id="TX_WAVELENGTHS",
            form_code="EXPOSURE",
            code="TX_WAVELENGTHS",
            unit="nm",
            value_kind="text",
            visits=treat_visits,
            section="wavelength settings",
            protocol_version=version,
            note="Source lists 590/680/780/830 nm treatment settings and separate three-wavelength device wording; AMD-WAVE unresolved.",
            enforced=False,
        ),
        _field(logical_field_id="AE_TERM", form_code="AE", code="AE_TERM", unit="text", value_kind="text", visits=all_visits, section="AE/safety", protocol_version=version, enforced=False),
        _field(logical_field_id="DS_STATUS", form_code="DS", code="DS_STATUS", unit="code", value_kind="text", visits=["V6"], section="disposition", protocol_version=version),
    ]
    forms = [
        {"form_code": "SCREENING", "coverage": "FIELD", "source": "11.x screening", "proposal": True},
        {"form_code": "CONSENT", "coverage": "FIELD", "source": "ICF", "proposal": True},
        {"form_code": "ELIGIBILITY", "coverage": "NAME_ONLY", "source": "inclusion/exclusion", "proposal": True, "note": "criteria text not copied"},
        {"form_code": "DEMOG", "coverage": "FIELD", "source": "demographics", "proposal": True},
        {"form_code": "MH", "coverage": "STAGED_NO_STABLE_KEY", "source": "medical history", "proposal": True},
        {"form_code": "CM", "coverage": "STAGED_NO_STABLE_KEY", "source": "concomitant medications", "proposal": True},
        {"form_code": "STUDY_EYE", "coverage": "FIELD", "source": "study eye designation", "proposal": True},
        {"form_code": "BCVA", "coverage": "FIELD", "source": "primary/secondary BCVA", "proposal": True},
        {"form_code": "OCT_DRUSEN", "coverage": "FIELD", "source": "OCT drusen volume/thickness", "proposal": True},
        {"form_code": "IOP", "coverage": "FIELD", "source": "IOP repeated", "proposal": True},
        {"form_code": "IMAGING", "coverage": "FIELD", "source": "fundus/FAF/slit-lamp/VF", "proposal": True},
        {"form_code": "EXPOSURE", "coverage": "FIELD", "source": "device treatment exposure", "proposal": True},
        {"form_code": "AE", "coverage": "STAGED_NO_STABLE_KEY", "source": "AE safety", "proposal": True},
        {"form_code": "DS", "coverage": "FIELD", "source": "disposition", "proposal": True},
        {
            "form_code": "REVIEW_FINDINGS",
            "coverage": "FINDINGS_ONLY",
            "source": "conflict review",
            "proposal": True,
            "findings": list(REVIEW_FINDINGS),
            "note": "Unresolved protocol conflicts; not active validation rules.",
        },
    ]
    return fields, forms


def install_amd_catalog() -> None:
    register_form_catalog(STUDY_ID, _amd_catalog)
