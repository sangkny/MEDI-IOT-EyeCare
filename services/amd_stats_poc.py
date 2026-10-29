"""Synthetic AMD statistical proof-of-concept. Not clinical evidence."""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass


STATS_VERSION = "amd-bcva-drusen-descriptive-v0.1"


@dataclass
class EyeObservation:
    subject_id: str
    study_id: str
    study_eye: str
    visit: str
    week: int | None
    bcva_letters: float | None
    drusen_vol: float | None
    drusen_thk: float | None
    fas_eligible: bool
    ss_eligible: bool


def synthetic_cohort(study_id: str = "MEDI-AMD-001") -> list[EyeObservation]:
    """Deterministic synthetic rows. Missing values preserved as None."""
    rows: list[EyeObservation] = []
    # subject A: complete FAS/SS
    for visit, week, bcva, vol, thk in (
        ("V2", 0, 55.0, 0.42, 85.0),
        ("V3", 5, 58.0, 0.40, 82.0),
        ("V5", 9, 60.0, 0.38, 80.0),
        ("V6", 21, 59.0, 0.37, 79.0),
    ):
        rows.append(EyeObservation(study_id=study_id, subject_id="SYN-A", study_eye="OD", visit=visit, week=week,
                                   bcva_letters=bcva, drusen_vol=vol, drusen_thk=thk, fas_eligible=True, ss_eligible=True))
    # subject B: missing week 21 BCVA, still FAS baseline present
    for visit, week, bcva, vol, thk in (
        ("V2", 0, 48.0, 0.55, 95.0),
        ("V3", 5, 50.0, 0.53, 93.0),
        ("V5", 9, None, 0.52, None),
        ("V6", 21, None, None, 90.0),
    ):
        rows.append(EyeObservation(study_id=study_id, subject_id="SYN-B", study_eye="OS", visit=visit, week=week,
                                   bcva_letters=bcva, drusen_vol=vol, drusen_thk=thk, fas_eligible=True, ss_eligible=True))
    # subject C: SS only (treated) but excluded from FAS by flag
    for visit, week, bcva, vol, thk in (
        ("V2", 0, 40.0, 0.60, 100.0),
        ("V3", 5, 41.0, 0.59, 99.0),
    ):
        rows.append(EyeObservation(study_id=study_id, subject_id="SYN-C", study_eye="OD", visit=visit, week=week,
                                   bcva_letters=bcva, drusen_vol=vol, drusen_thk=thk, fas_eligible=False, ss_eligible=True))
    return rows


def _change(baseline: float | None, follow: float | None) -> float | None:
    if baseline is None or follow is None:
        return None
    return follow - baseline


def _summary(values: list[float | None]) -> dict:
    present = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    missing = len(values) - len(present)
    if not present:
        return {"n": 0, "missing": missing, "mean": None, "sd": None, "min": None, "max": None}
    return {
        "n": len(present),
        "missing": missing,
        "mean": statistics.fmean(present),
        "sd": statistics.stdev(present) if len(present) > 1 else 0.0,
        "min": min(present),
        "max": max(present),
    }


def analyze(rows: list[EyeObservation]) -> dict:
    by_subject = {}
    for row in rows:
        by_subject.setdefault(row.subject_id, []).append(row)
    bcva_changes_w5 = []
    bcva_changes_w9 = []
    bcva_changes_w21 = []
    fas_ids = set()
    ss_ids = set()
    for subject_id, observations in by_subject.items():
        if any(item.fas_eligible for item in observations):
            fas_ids.add(subject_id)
        if any(item.ss_eligible for item in observations):
            ss_ids.add(subject_id)
        if subject_id not in fas_ids:
            continue
        indexed = {item.visit: item for item in observations}
        base = indexed.get("V2")
        if base is None:
            continue
        for visit, bucket in (("V3", bcva_changes_w5), ("V5", bcva_changes_w9), ("V6", bcva_changes_w21)):
            follow = indexed.get(visit)
            bucket.append(_change(None if base is None else base.bcva_letters,
                                  None if follow is None else follow.bcva_letters))
    return {
        "stats_version": STATS_VERSION,
        "disclaimer": "SYNTHETIC_PROOF_OF_CONCEPT_NOT_CLINICAL_EVIDENCE",
        "exploratory_only": True,
        "study_eye_metadata_present": all(row.study_eye in {"OD", "OS"} for row in rows),
        "populations": {"FAS": sorted(fas_ids), "SS": sorted(ss_ids)},
        "bcva_change_from_baseline": {
            "week5_visit3": _summary(bcva_changes_w5),
            "week9_visit5": _summary(bcva_changes_w9),
            "week21_visit6": _summary(bcva_changes_w21),
        },
        "missing_data_preserved": any(row.bcva_letters is None or row.drusen_vol is None for row in rows),
        "observations": [asdict(row) for row in rows],
    }


def dump(path) -> dict:
    result = analyze(synthetic_cohort())
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
