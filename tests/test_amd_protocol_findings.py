"""Protocol conflict classification regression. No confidential body embedded."""
from __future__ import annotations

from services.amd_protocol_findings import DOCUMENT_STATUS, FINDINGS, SOURCE_SHA256, finding_classifications


def test_amd_wave_not_three_only():
    wave = FINDINGS["AMD-WAVE"]
    assert wave["classification"] == "CONFIRMED_CONFLICT"
    assert wave["wavelengths_nm"] == [590, 680, 780, 830]
    assert "three-wavelength-only" in wave["note"] or "three-wavelength" in wave["note"]


def test_sample_size_not_automatic_hard_conflict():
    row = FINDINGS["AMD-N15-N16"]
    assert row["classification"] == "POSSIBLE_CONFLICT"
    assert "deliberate pilot" in row["note"].lower() or "pilot" in row["note"].lower()


def test_retention_flagged_without_policy_change():
    row = FINDINGS["AMD-DATA-RETENTION"]
    assert row["classification"] == "CONFIRMED_CONFLICT"
    assert "no deletion" in row["note"].lower() or "without review" in row["note"].lower()


def test_document_draft_and_sha():
    assert DOCUMENT_STATUS == "DRAFT"
    assert len(SOURCE_SHA256) == 64
    classes = finding_classifications()
    assert classes["AMD-SCHED-V6"] == "CONFIRMED_CONFLICT"
    assert classes["AMD-DESIGN-RAND"] == "CONFIRMED_CONFLICT"
    assert classes["AMD-EP-VISIT"] == "POSSIBLE_CONFLICT"
    assert classes["AMD-TX-SETTINGS"] == "POSSIBLE_CONFLICT"
