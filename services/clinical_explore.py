"""대상자와 Visit 조회 기초. 화면이 아니라 인가된 읽기 서비스다."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalObservation,
    DataQualityFinding,
    ImportLink,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from services.clinical_records import ClinicalRecordError, _require_site_member


def _subject_for_actor(session: Session, subject_id: str, actor_user_id: str) -> StudySubject:
    subject = session.get(StudySubject, subject_id)
    if subject is None:
        raise ClinicalRecordError("대상자가 없습니다.")
    _require_site_member(session, subject.site_id, actor_user_id)
    return subject


def subject_visit_history(
    session: Session,
    *,
    subject_id: str,
    actor_user_id: str,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
    site_id: str | None = None,
) -> dict:
    subject = _subject_for_actor(session, subject_id, actor_user_id)
    if site_id is not None and subject.site_id != site_id:
        raise ClinicalRecordError("다른 사이트의 대상자입니다.")
    visits = list(session.scalars(
        select(StudyVisit)
        .where(StudyVisit.subject_id == subject.id)
        .order_by(StudyVisit.occurred_on, StudyVisit.visit_code)
    ).all())
    if occurred_from is not None:
        visits = [visit for visit in visits if visit.occurred_on >= occurred_from]
    if occurred_to is not None:
        visits = [visit for visit in visits if visit.occurred_on <= occurred_to]
    history = []
    for visit in visits:
        observations = list(session.scalars(
            select(ClinicalObservation).where(ClinicalObservation.visit_id == visit.id)
        ).all())
        findings = session.scalar(
            select(DataQualityFinding.id).where(DataQualityFinding.visit_id == visit.id)
        )
        links = list(session.scalars(
            select(ImportLink).where(ImportLink.target_id.in_([row.id for row in observations] or [""]))
        ).all()) if observations else []
        history.append({
            "visit_id": visit.id,
            "visit_code": visit.visit_code,
            "occurred_on": visit.occurred_on.isoformat(),
            "observations": [
                {
                    "id": row.id,
                    "code": row.code,
                    "laterality": row.laterality,
                    "repeat_index": row.repeat_index,
                    "record_status": row.record_status,
                    "source": row.source,
                }
                for row in observations
            ],
            "quality_finding_present": findings is not None,
            "import_batch_ids": sorted({link.batch_id for link in links}),
        })
    return {
        "study_id": subject.study_id,
        "site_id": subject.site_id,
        "subject_id": subject.id,
        "subject_code": subject.subject_code,
        "visits": history,
    }


def list_study_visits(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    site_id: str | None = None,
    occurred_from: date | None = None,
    occurred_to: date | None = None,
) -> list[dict]:
    member_site_ids = set(session.scalars(
        select(StudySite.id)
        .join(StudySiteMember, StudySiteMember.site_id == StudySite.id)
        .where(StudySite.study_id == study_id, StudySiteMember.user_id == actor_user_id)
    ).all())
    if site_id is not None:
        if site_id not in member_site_ids:
            raise ClinicalRecordError("사이트 구성원이 아닙니다.")
        member_site_ids = {site_id}
    if not member_site_ids:
        raise ClinicalRecordError("연구 구성원이 아닙니다.")
    rows = session.execute(
        select(StudyVisit, StudySubject)
        .join(StudySubject, StudySubject.id == StudyVisit.subject_id)
        .where(StudySubject.study_id == study_id, StudySubject.site_id.in_(member_site_ids))
        .order_by(StudyVisit.occurred_on)
    ).all()
    result = []
    for visit, subject in rows:
        if occurred_from is not None and visit.occurred_on < occurred_from:
            continue
        if occurred_to is not None and visit.occurred_on > occurred_to:
            continue
        result.append({
            "visit_id": visit.id,
            "visit_code": visit.visit_code,
            "occurred_on": visit.occurred_on.isoformat(),
            "subject_id": subject.id,
            "site_id": subject.site_id,
        })
    return result
