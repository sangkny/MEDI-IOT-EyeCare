"""Phase 010 증례 대시보드. 읽기만 하고 원본 값을 바꾸지 않는다.

규칙 활성화, R1, 방문 허용기간 판정, 자동 확정, 자동 잠금은 하지 않는다.
배정 값은 조회하지 않는다.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    ClinicalQuery,
    DataQualityFinding,
    ImportBatch,
    ImportDiscrepancy,
    ImportStagingRow,
    StudySite,
    StudySubject,
    StudyVisit,
)
from services.clinical_import import aggregate_workbook
from services.clinical_protocol_rules import visit_assessments
from services.clinical_records import ClinicalRecordError, _require_site_member

MEASURES = {
    "TBUT": "s",
    "OSDI_SCORE": "score",
    "SCHIRMER": "mm/5min",
}
VISIT_ORDER = ("V1", "V2", "V3", "V4", "V5", "V6")
SCHEDULE_KEY = {"TBUT": "TBUT", "OSDI_SCORE": "OSDI", "SCHIRMER": "SCHIRMER"}
SAFETY = {
    "enable_r1": False,
    "protocol_advisory_id": None,
    "window_check": False,
    "unapproved_rules_active": False,
    "automatic_correction": False,
    "automatic_finalize": False,
    "automatic_lock": False,
    "blinding_preserved": True,
}


def _site(session: Session, study_id: str, site_id: str, actor_user_id: str) -> StudySite:
    _require_site_member(session, site_id, actor_user_id)
    site = session.get(StudySite, site_id)
    if site is None or site.study_id != study_id:
        raise ClinicalRecordError("사이트가 이 연구에 속하지 않습니다.")
    return site


def _quartile(ordered: list[float], fraction: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _box(values: list[float]) -> dict:
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "min": None, "q1": None, "median": None, "q3": None, "max": None}
    return {
        "n": len(ordered),
        "min": ordered[0],
        "q1": _quartile(ordered, 0.25),
        "median": _quartile(ordered, 0.5),
        "q3": _quartile(ordered, 0.75),
        "max": ordered[-1],
    }


def _visit_rank(code: str) -> tuple[int, str]:
    if code in VISIT_ORDER:
        return (VISIT_ORDER.index(code), code)
    return (len(VISIT_ORDER), code)


def _population(status: str) -> str:
    return "FINAL" if status == "final" else "DRAFT"


def build_case_dashboard(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    subject_code: str | None = None,
) -> dict:
    _site(session, study_id, site_id, actor_user_id)
    subjects = session.scalars(
        select(StudySubject).where(
            StudySubject.study_id == study_id,
            StudySubject.site_id == site_id,
        )
    ).all()
    subject_ids = [row.id for row in subjects]
    visits = []
    if subject_ids:
        visits = session.scalars(
            select(StudyVisit).where(StudyVisit.subject_id.in_(subject_ids))
        ).all()
    visit_ids = [row.id for row in visits]
    observations = []
    if visit_ids:
        observations = session.scalars(
            select(ClinicalObservation).where(ClinicalObservation.visit_id.in_(visit_ids))
        ).all()
    subject_by_id = {row.id: row for row in subjects}
    visit_by_id = {row.id: row for row in visits}
    status_counts = {"draft": 0, "final": 0, "other": 0}
    for row in observations:
        key = row.record_status if row.record_status in {"draft", "final"} else "other"
        status_counts[key] += 1
    batches = session.scalars(
        select(ImportBatch).where(
            ImportBatch.study_id == study_id,
            ImportBatch.site_id == site_id,
        )
    ).all()
    batch_ids = [row.id for row in batches]
    staging_counts: dict[str, int] = {}
    if batch_ids:
        rows = session.execute(
            select(ImportStagingRow.status, func.count())
            .where(ImportStagingRow.batch_id.in_(batch_ids))
            .group_by(ImportStagingRow.status)
        ).all()
        staging_counts = {status: count for status, count in rows}
    finding_rows = session.execute(
        select(DataQualityFinding.status, func.count())
        .where(DataQualityFinding.study_id == study_id)
        .group_by(DataQualityFinding.status)
    ).all()
    query_rows = session.execute(
        select(ClinicalQuery.status, func.count())
        .where(ClinicalQuery.study_id == study_id, ClinicalQuery.site_id == site_id)
        .group_by(ClinicalQuery.status)
    ).all()
    discrepancy_count = session.scalar(
        select(func.count()).select_from(ImportDiscrepancy).where(
            ImportDiscrepancy.study_id == study_id,
        )
    ) or 0
    selected = None
    if subject_code is not None:
        if len(subject_code) > 64:
            raise ClinicalRecordError("대상자 코드가 너무 깁니다.")
        selected = next((row for row in subjects if row.subject_code == subject_code), None)
        if selected is None:
            raise ClinicalRecordError("대상자가 이 사이트에 없습니다.")
    schedule = visit_assessments()
    scoped_visits = [row for row in visits if selected is None or row.subject_id == selected.id]
    scoped_observations = [row for row in observations if row.visit_id in {visit.id for visit in scoped_visits}]
    boxes: dict[str, dict[tuple, list[float]]] = {"FINAL": {}, "DRAFT": {}}
    nonnumeric = []
    for row in scoped_observations:
        if row.code not in MEASURES:
            continue
        visit = visit_by_id[row.visit_id]
        if row.value_number is None:
            if row.value_text:
                nonnumeric.append({
                    "code": row.code,
                    "visit_code": visit.visit_code,
                    "laterality": row.laterality,
                    "record_status": _population(row.record_status),
                })
            continue
        key = (row.code, row.laterality, row.method, visit.visit_code)
        boxes[_population(row.record_status)].setdefault(key, []).append(float(row.value_number))
    def _series(population: str) -> list[dict]:
        rendered = []
        for (code, laterality, method, visit_code), values in boxes[population].items():
            rendered.append({
                "population": population,
                "code": code,
                "unit": MEASURES[code],
                "laterality": laterality,
                "method": method,
                "recalculated": False,
                "visits": [{"visit_code": visit_code, **_box(values)}],
            })
        rendered.sort(key=lambda item: (item["code"], item["laterality"], item["method"], _visit_rank(item["visits"][0]["visit_code"])))
        merged: list[dict] = []
        for item in rendered:
            previous = next((
                row for row in merged
                if row["code"] == item["code"] and row["laterality"] == item["laterality"] and row["method"] == item["method"]
            ), None)
            if previous is None:
                merged.append(item)
            else:
                previous["visits"].extend(item["visits"])
        for row in merged:
            row["visits"].sort(key=lambda visit: _visit_rank(visit["visit_code"]))
        return merged
    coverage = []
    for code in MEASURES:
        by_visit: dict[str, dict[str, int]] = {}
        for visit in scoped_visits:
            if not schedule.get(visit.visit_code, {}).get(SCHEDULE_KEY[code], False):
                continue
            bucket = by_visit.setdefault(visit.visit_code, {"expected": 0, "numeric_final": 0, "numeric_draft": 0, "nonnumeric": 0})
            bucket["expected"] += 1
        for row in scoped_observations:
            if row.code != code:
                continue
            visit_code = visit_by_id[row.visit_id].visit_code
            if visit_code not in by_visit:
                continue
            if row.value_number is not None and row.record_status == "final":
                by_visit[visit_code]["numeric_final"] += 1
            elif row.value_number is not None:
                by_visit[visit_code]["numeric_draft"] += 1
            elif row.value_text:
                by_visit[visit_code]["nonnumeric"] += 1
        for visit_code in sorted(by_visit, key=_visit_rank):
            bucket = by_visit[visit_code]
            bucket["absent"] = max(bucket["expected"] - bucket["numeric_final"] - bucket["numeric_draft"] - bucket["nonnumeric"], 0)
            coverage.append({"code": code, "visit_code": visit_code, "unit": MEASURES[code], **bucket})
    subject_series = {"FINAL": [], "DRAFT": []}
    provenance = []
    if selected is not None:
        for row in scoped_observations:
            if row.code not in MEASURES:
                continue
            visit = visit_by_id[row.visit_id]
            provenance.append({
                "visit_code": visit.visit_code,
                "code": row.code,
                "laterality": row.laterality,
                "method": row.method,
                "repeat_index": row.repeat_index,
                "record_status": _population(row.record_status),
                "source": row.source,
                "unit": row.unit or MEASURES[row.code],
                "unit_origin": "observation" if row.unit else "protocol_metadata",
                "numeric": row.value_number is not None,
            })
            if row.value_number is None:
                continue
            subject_series[_population(row.record_status)].append({
                "visit_code": visit.visit_code,
                "code": row.code,
                "laterality": row.laterality,
                "method": row.method,
                "repeat_index": row.repeat_index,
                "value_number": float(row.value_number),
                "unit": row.unit or MEASURES[row.code],
                "unit_origin": "observation" if row.unit else "protocol_metadata",
                "record_status": _population(row.record_status),
                "source": row.source,
                "recalculated": False,
            })
        for population in subject_series.values():
            population.sort(key=lambda item: (_visit_rank(item["visit_code"]), item["code"], item["laterality"], item["repeat_index"]))
        provenance.sort(key=lambda item: (_visit_rank(item["visit_code"]), item["code"], item["laterality"], item["repeat_index"]))
    visit_rows = []
    if selected is None:
        for code in VISIT_ORDER:
            matched = [row for row in visits if row.visit_code == code]
            if not matched:
                continue
            visit_rows.append({
                "visit_code": code,
                "subject_count": len({row.subject_id for row in matched}),
                "draft_count": sum(1 for obs in observations if visit_by_id[obs.visit_id].visit_code == code and obs.record_status == "draft"),
                "final_count": sum(1 for obs in observations if visit_by_id[obs.visit_id].visit_code == code and obs.record_status == "final"),
            })
    else:
        visit_rows = [
            {
                "visit_code": row.visit_code,
                "occurred_on": row.occurred_on.isoformat(),
                "draft_count": sum(1 for obs in observations if obs.visit_id == row.id and obs.record_status == "draft"),
                "final_count": sum(1 for obs in observations if obs.visit_id == row.id and obs.record_status == "final"),
            }
            for row in sorted(scoped_visits, key=lambda item: _visit_rank(item.visit_code))
        ]
    return {
        "study_id": study_id,
        "site_id": site_id,
        "safety": SAFETY,
        "overview": {
            "subject_count": len(subjects),
            "visit_count": len(visits),
            "observation_status": status_counts,
            "staged_row_count": staging_counts.get("staged", 0) + staging_counts.get("subject_level_staged", 0),
            "unresolved_row_count": sum(
                count for status, count in staging_counts.items() if "unresolved" in status or status.endswith("error")
            ),
        },
        "subjects": [
            {
                "subject_code": row.subject_code,
                "visit_count": sum(1 for visit in visits if visit.subject_id == row.id),
                "draft_count": sum(
                    1 for obs in observations
                    if visit_by_id[obs.visit_id].subject_id == row.id and obs.record_status == "draft"
                ),
                "final_count": sum(
                    1 for obs in observations
                    if visit_by_id[obs.visit_id].subject_id == row.id and obs.record_status == "final"
                ),
            }
            for row in subjects
        ],
        "visits": visit_rows,
        "analytics": {
            "final_descriptive": _series("FINAL"),
            "draft_exploratory": _series("DRAFT"),
            "coverage": coverage,
            "nonnumeric_count": len(nonnumeric),
            "subject_series": subject_series if selected is not None else None,
            "provenance": provenance,
            "osdi_recalculated": False,
        },
        "quality": {
            "findings": {status: count for status, count in finding_rows},
            "queries": {status: count for status, count in query_rows},
        },
        "imports": {
            "batch_count": len(batches),
            "mapping_versions": sorted({row.mapping_version for row in batches}),
            "staging_status": staging_counts,
            "discrepancy_count": discrepancy_count,
            "persisted_payload": False,
        },
    }


def validate_case_export(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    content: bytes | None,
) -> dict:
    """반출 파일을 저장하지 않고 집계만 반환한다."""
    _site(session, study_id, site_id, actor_user_id)
    if not content:
        return {"persisted": False, "mode": "no_file", "real_export_loaded": False, "safety": SAFETY}
    try:
        summary = aggregate_workbook(content)
    except Exception as exc:
        raise ClinicalRecordError("반출 파일을 집계할 수 없습니다.") from exc
    summary["persisted"] = False
    summary["mode"] = "read_only_aggregate"
    summary["real_export_loaded"] = False
    summary["safety"] = SAFETY
    return summary
