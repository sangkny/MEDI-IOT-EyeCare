"""Sanitized AMD Protocol finding classifications for tests and reports.

Confidential Protocol text is not embedded. Classifications come from the
authorized local DOCX recheck (scripts/_recheck_amd_findings.py).
"""
from __future__ import annotations

from typing import Final

SOURCE_SHA256: Final = "85B946928FFCC33FAF1C858D8BC745186BAE3298B737B8B11AED9A3EC54330F5"
DOCUMENT_STATUS: Final = "DRAFT"

# Evidence-backed classifications after 2026-10-29 recheck.
FINDINGS: Final[dict[str, dict]] = {
    "AMD-WAVE": {
        "classification": "CONFIRMED_CONFLICT",
        "note": (
            "Protocol contains three-wavelength device descriptions "
            "(e.g. 680/780/830 nm) and four-wavelength treatment settings "
            "(590, 680, 780, 830 nm with irradiance values). "
            "Do not classify the full Protocol as three-wavelength-only."
        ),
        "wavelengths_nm": [590, 680, 780, 830],
        "locations": [
            "paragraph ~87 treatment settings 590/680/780/830 nm",
            "device tables ~table 12 LED rows 590/680/780/830",
            "three-wavelength MEDI-EYE wording elsewhere",
        ],
    },
    "AMD-SCHED-V6": {
        "classification": "CONFIRMED_CONFLICT",
        "note": "Schedule table lists Visit 1–5; procedure text references Visit 6 (21w EOS).",
    },
    "AMD-EP-VISIT": {
        "classification": "POSSIBLE_CONFLICT",
        "note": "Primary BCVA change at weeks 5 and 9; Visit 6 / week 21 appears in secondary/procedure text.",
    },
    "AMD-N15-N16": {
        "classification": "POSSIBLE_CONFLICT",
        "note": (
            "Calculated sample size 16 and chosen pilot enrollment 15 coexist. "
            "Do not treat them as identical mandatory requirements; confirm deliberate pilot decision."
        ),
    },
    "AMD-DATA-RETENTION": {
        "classification": "CONFIRMED_CONFLICT",
        "note": (
            "Withdrawal-related destruction wording versus retention of previously collected "
            "dropout records. Flag only; no deletion/preservation policy change without review."
        ),
    },
    "AMD-DESIGN-RAND": {
        "classification": "CONFIRMED_CONFLICT",
        "note": "Single-arm design coexists with randomization terminology (무작위배정).",
    },
    "AMD-TX-SETTINGS": {
        "classification": "POSSIBLE_CONFLICT",
        "note": "Wavelength, power/irradiance, mode, exposure duration and treatment frequency require separate cross-check.",
    },
}


def finding_classifications() -> dict[str, str]:
    return {key: value["classification"] for key, value in FINDINGS.items()}
