"""계획서 기반 설문 초안, OSDI 채점, 통계.

기존 questionnaire_* 테이블을 재사용한다. 문항 원문은 저작권상 저장하지 않고
문항 코드와 점수 의미만 둔다. 채점 결과는 원본 응답과 분리한다.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ProtocolDocument,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireScoreResult,
    QuestionnaireVersion,
    StudySite,
    StudySubject,
    StudyVisit,
    VisitFormAssignment,
)
from services.clinical_protocol_rules import osdi_form_visits
from services.clinical_records import (
    ClinicalRecordError,
    _audit,
    _require_site_member,
    define_questionnaire,
    finalize_response,
    publish_questionnaire_version,
    save_response_item,
    start_response,
)
from services.protocol_ecrf import _member

SCORING_VERSION = "osdi-medi-des-001-v1"
OSDI_CODE = "OSDI"


def _osdi_items(protocol_version: str) -> list[dict]:
    visits = osdi_form_visits()
    applicable = visits["v13_form_visits"] if protocol_version == "1.3" else visits["form_visits"]
    items = []
    for index in range(1, 13):
        items.append({
            "code": f"OSQ{index}",
            "type": "number",
            "min": 0,
            "max": 4,
            "required": False,
            "allows_not_applicable": index >= 6,
            "text_policy": "SOURCE_BOUND_NOT_REPRODUCED",
            "source_reference": "부록 1",
            "protocol_version": protocol_version,
            "visits": applicable.split(","),
            "proposal": True,
        })
    items.append({
        "code": "OSSCORE",
        "type": "number",
        "required": False,
        "reported_score": True,
        "text_policy": "SOURCE_BOUND_NOT_REPRODUCED",
        "source_reference": "부록 1",
        "protocol_version": protocol_version,
        "visits": applicable.split(","),
        "proposal": True,
    })
    return items


def generate_osdi_draft(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    actor_role: str,
    document_id: str,
) -> dict:
    """기존 설문 정의/버전 테이블에 OSDI 초안을 추가한다."""
    _member(session, study_id, site_id, actor_user_id)
    document = session.get(ProtocolDocument, document_id)
    if document is None or document.study_id != study_id:
        raise ClinicalRecordError("계획서 버전이 없습니다.")
    items = _osdi_items(document.version_label)
    definition = session.scalar(
        select(QuestionnaireDefinition).where(
            QuestionnaireDefinition.study_id == study_id,
            QuestionnaireDefinition.code == OSDI_CODE,
        )
    )
    if definition is None:
        definition = define_questionnaire(
            session, study_id=study_id, code=OSDI_CODE, title="OSDI draft", actor_user_id=actor_user_id,
        )
    next_number = (
        session.scalar(
            select(func.coalesce(func.max(QuestionnaireVersion.version_number), 0)).where(
                QuestionnaireVersion.definition_id == definition.id,
            )
        )
        or 0
    ) + 1
    payload = {
        "lifecycle": "DRAFT",
        "scoring": {
            "algorithm": "OSDI",
            "version": SCORING_VERSION,
            "formula": "(sum of scored responses x 25) / answered_count",
            "rounding": "UNSPECIFIED",
            "proposal": True,
        },
        "language": "ko",
        "translation_version": None,
        "protocol_version": document.version_label,
        "source_sha256": document.source_sha256,
        "items": items,
    }
    version = publish_questionnaire_version(
        session,
        definition_id=definition.id,
        version_number=next_number,
        items_json=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        actor_user_id=actor_user_id,
    )
    # publish already audited once; attach chain metadata with protocol version
    _audit(
        session,
        study_id=study_id,
        site_id=site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="questionnaire_drafted",
        target_type="questionnaire_version",
        target_id=version.id,
        payload={
            "definition_id": definition.id,
            "version_number": version.version_number,
            "content_hash": version.content_hash,
            "proposal": True,
        },
        reason="계획서에서 OSDI 설문 초안 생성",
        protocol_version=document.version_label,
        link_chain=True,
    )
    visits = items[0]["visits"]
    for visit_code in visits:
        exists = session.scalar(
            select(VisitFormAssignment).where(
                VisitFormAssignment.study_id == study_id,
                VisitFormAssignment.visit_code == visit_code,
                VisitFormAssignment.definition_id == definition.id,
            )
        )
        if exists is None:
            session.add(VisitFormAssignment(
                study_id=study_id, visit_code=visit_code, definition_id=definition.id,
            ))
    session.flush()
    return {
        "definition_id": definition.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "content_hash": version.content_hash,
        "protocol_version": document.version_label,
        "visits": visits,
        "item_count": len(items),
        "lifecycle": "DRAFT",
        "proposal": True,
    }


def _items_payload(version: QuestionnaireVersion) -> dict:
    parsed = json.loads(version.items_json)
    if isinstance(parsed, list):
        return {"items": parsed, "scoring": {"version": SCORING_VERSION}}
    return parsed


def score_osdi_response(
    session: Session,
    *,
    response_id: str,
    actor_user_id: str,
    actor_role: str,
    reported_score: float | None = None,
) -> QuestionnaireScoreResult:
    response = session.get(QuestionnaireResponse, response_id)
    if response is None:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    visit = session.get(StudyVisit, response.visit_id)
    if visit is None:
        raise ClinicalRecordError("Visit 가 없습니다.")
    _require_site_member(session, visit.subject.site_id, actor_user_id)
    payload = _items_payload(response.version)
    specs = {item["code"]: item for item in payload["items"]}
    answers = {
        item.item_code: json.loads(item.value_json)
        for item in session.scalars(
            select(QuestionnaireResponseItem).where(QuestionnaireResponseItem.response_id == response.id)
        )
    }
    scored: list[int] = []
    na_count = 0
    blank = 0
    evidence = []
    for index in range(1, 13):
        code = f"OSQ{index}"
        raw = answers.get(code)
        allows_na = bool(specs.get(code, {}).get("allows_not_applicable"))
        if raw is None or raw == "":
            blank += 1
            evidence.append({"item": code, "kind": "blank"})
            continue
        if allows_na and str(raw).upper() in {"NA", "N/A", "해당없음"}:
            na_count += 1
            evidence.append({"item": code, "kind": "not_applicable"})
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            raise ClinicalRecordError(f"문항 {code} 점수가 올바르지 않습니다.")
        if number < 0 or number > 4:
            raise ClinicalRecordError(f"문항 {code} 는 0부터 4까지입니다.")
        scored.append(number)
        evidence.append({"item": code, "kind": "scored", "value_protected": True})
    if not scored:
        calculated = None
        status = "INCOMPLETE"
    else:
        calculated = sum(scored) * 25 / len(scored)
        status = "ADVISORY"
    if reported_score is None and "OSSCORE" in answers:
        try:
            reported_score = float(answers["OSSCORE"])
        except (TypeError, ValueError):
            reported_score = None
    revision = (
        session.scalar(
            select(func.coalesce(func.max(QuestionnaireScoreResult.revision), 0)).where(
                QuestionnaireScoreResult.response_id == response.id,
                QuestionnaireScoreResult.scoring_version == SCORING_VERSION,
            )
        )
        or 0
    ) + 1
    row = QuestionnaireScoreResult(
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        response_id=response.id,
        questionnaire_version_id=response.version_id,
        scoring_version=SCORING_VERSION,
        revision=revision,
        answered_count=len(scored),
        not_applicable_count=na_count,
        blank_count=blank,
        score_sum=sum(scored) if scored else None,
        calculated_score=calculated,
        reported_score=reported_score,
        status=status,
        evidence_json=json.dumps({
            "formula": "(sum x 25) / answered_count",
            "rounding": "UNSPECIFIED",
            "items": evidence,
            "original_values_mutated": False,
        }, ensure_ascii=False, sort_keys=True),
        created_by=actor_user_id,
    )
    session.add(row)
    session.flush()
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="questionnaire_scored",
        target_type="questionnaire_score",
        target_id=row.id,
        payload={
            "response_id": response.id,
            "scoring_version": SCORING_VERSION,
            "revision": revision,
            "status": status,
            "value_protected": True,
        },
        reason="OSDI 권고 채점",
        link_chain=True,
    )
    return row


def questionnaire_stats(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    definition_id: str | None = None,
) -> dict:
    _member(session, study_id, site_id, actor_user_id)
    subject_ids = select(StudySubject.id).where(
        StudySubject.study_id == study_id, StudySubject.site_id == site_id,
    )
    visit_ids = select(StudyVisit.id).where(StudyVisit.subject_id.in_(subject_ids))
    stmt = select(QuestionnaireResponse).where(QuestionnaireResponse.visit_id.in_(visit_ids))
    if definition_id:
        version_ids = select(QuestionnaireVersion.id).where(
            QuestionnaireVersion.definition_id == definition_id,
        )
        stmt = stmt.where(QuestionnaireResponse.version_id.in_(version_ids))
    responses = list(session.scalars(stmt).all())
    by_status = Counter(row.status for row in responses)
    version_ids_used = {row.version_id for row in responses}
    item_counts: Counter[str] = Counter()
    na_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    scores_final: list[float] = []
    scores_draft: list[float] = []
    trajectories: dict[str, list[dict]] = {}
    for response in responses:
        visit = session.get(StudyVisit, response.visit_id)
        items = list(session.scalars(
            select(QuestionnaireResponseItem).where(QuestionnaireResponseItem.response_id == response.id)
        ))
        answered = {item.item_code: json.loads(item.value_json) for item in items}
        payload = _items_payload(response.version)
        for spec in payload["items"]:
            code = spec["code"]
            if code.startswith("OSQ"):
                raw = answered.get(code)
                if raw is None or raw == "":
                    missing_counts[code] += 1
                elif str(raw).upper() in {"NA", "N/A", "해당없음"}:
                    na_counts[code] += 1
                else:
                    item_counts[f"{code}:{raw}"] += 1
        score = session.scalar(
            select(QuestionnaireScoreResult)
            .where(QuestionnaireScoreResult.response_id == response.id)
            .order_by(QuestionnaireScoreResult.revision.desc())
            .limit(1)
        )
        if score is not None and score.calculated_score is not None:
            bucket = scores_final if response.status == "final" else scores_draft
            bucket.append(float(score.calculated_score))
            subject_code = visit.subject.subject_code if visit is not None else "unknown"
            trajectories.setdefault(subject_code, []).append({
                "visit_code": visit.visit_code if visit else None,
                "status": response.status,
                "questionnaire_version_id": response.version_id,
                "score_status": score.status,
                "has_score": True,
            })
    return {
        "study_id": study_id,
        "site_id": site_id,
        "denominator_responses": len(responses),
        "status_counts": dict(by_status),
        "questionnaire_versions": sorted(version_ids_used),
        "item_response_counts": dict(item_counts),
        "not_applicable_counts": dict(na_counts),
        "missing_counts": dict(missing_counts),
        "score_distributions": {
            "final": _distribution(scores_final),
            "draft": _distribution(scores_draft),
            "combined": False,
        },
        "trajectories": trajectories,
        "version_comparison": "separate",
        "blinding_preserved": True,
    }


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None}
    return {
        "n": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def open_questionnaire_response(
    session: Session,
    *,
    version_id: str,
    visit_id: str,
    actor_user_id: str,
    actor_role: str,
) -> QuestionnaireResponse:
    response = start_response(
        session, version_id=version_id, visit_id=visit_id, recorded_by=actor_user_id, actor_user_id=actor_user_id,
    )
    visit = session.get(StudyVisit, visit_id)
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="questionnaire_response_started",
        target_type="questionnaire_response",
        target_id=response.id,
        payload={"version_id": version_id, "visit_id": visit_id},
        reason="설문 응답 시작",
        link_chain=True,
    )
    return response


def _validate_item_value(session: Session, response_id: str, item_code: str, value) -> None:
    response = session.get(QuestionnaireResponse, response_id)
    if response is None:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    specs = {item.get("code"): item for item in _items_payload(response.version)["items"]}
    spec = specs.get(item_code)
    if spec is None:
        raise ClinicalRecordError("버전에 없는 문항입니다.")
    if value is None or value == "":
        return
    if spec.get("allows_not_applicable") and str(value).upper() in {"NA", "N/A", "해당없음"}:
        return
    if spec.get("type") == "number":
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ClinicalRecordError(f"문항 {item_code} 값이 올바르지 않습니다.") from exc
        if "min" in spec and number < float(spec["min"]):
            raise ClinicalRecordError(f"문항 {item_code} 는 최소 {spec['min']} 입니다.")
        if "max" in spec and number > float(spec["max"]):
            raise ClinicalRecordError(f"문항 {item_code} 는 최대 {spec['max']} 입니다.")


def record_questionnaire_item(
    session: Session,
    *,
    response_id: str,
    actor_user_id: str,
    actor_role: str,
    item_code: str,
    value,
    reason: str | None = None,
) -> QuestionnaireResponseItem:
    _validate_item_value(session, response_id, item_code, value)
    item = save_response_item(
        session,
        response_id,
        actor_user_id=actor_user_id,
        item_code=item_code,
        value_json=json.dumps(value, ensure_ascii=False),
    )
    response = session.get(QuestionnaireResponse, response_id)
    visit = session.get(StudyVisit, response.visit_id)
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="questionnaire_item_saved",
        target_type="questionnaire_response_item",
        target_id=item.id,
        payload={
            "response_id": response_id,
            "item_code": item_code,
            "questionnaire_version_id": response.version_id,
            "value_protected": True,
            "reason": reason,
        },
        reason=reason or "설문 문항 저장",
        link_chain=True,
    )
    return item


def finalize_questionnaire_response(
    session: Session,
    *,
    response_id: str,
    actor_user_id: str,
    actor_role: str,
) -> QuestionnaireResponse:
    response = finalize_response(session, response_id, actor_user_id=actor_user_id)
    visit = session.get(StudyVisit, response.visit_id)
    _audit(
        session,
        study_id=visit.subject.study_id,
        site_id=visit.subject.site_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action="questionnaire_response_finalized",
        target_type="questionnaire_response",
        target_id=response.id,
        payload={"version_id": response.version_id, "status": response.status},
        reason="설문 응답 확정",
        link_chain=True,
    )
    return response


def compare_questionnaire_versions(
    session: Session,
    *,
    study_id: str,
    earlier_id: str,
    later_id: str,
) -> dict:
    earlier = session.get(QuestionnaireVersion, earlier_id)
    later = session.get(QuestionnaireVersion, later_id)
    if earlier is None or later is None:
        raise ClinicalRecordError("설문 버전이 없습니다.")
    if earlier.definition.study_id != study_id or later.definition.study_id != study_id:
        raise ClinicalRecordError("설문이 이 연구에 없습니다.")
    left = _items_payload(earlier)
    right = _items_payload(later)
    left_codes = {item["code"]: item for item in left["items"]}
    right_codes = {item["code"]: item for item in right["items"]}
    changes = []
    for code in sorted(set(left_codes) | set(right_codes)):
        old = left_codes.get(code)
        new = right_codes.get(code)
        if old is None:
            kind = "ADDED"
        elif new is None:
            kind = "REMOVED"
        elif old.get("visits") != new.get("visits"):
            kind = "CHANGED_VISIT_SCHEDULE"
        else:
            kind = "UNCHANGED"
        changes.append({
            "item_code": code,
            "classification": kind,
            "earlier_visits": None if old is None else old.get("visits"),
            "later_visits": None if new is None else new.get("visits"),
            "mapping": "REVIEW_REQUIRED" if kind in {"REMOVED", "ADDED"} else "COMPATIBLE",
        })
    return {
        "earlier_version_id": earlier.id,
        "later_version_id": later.id,
        "earlier_hash": earlier.content_hash,
        "later_hash": later.content_hash,
        "immutable": True,
        "overwrites_responses": False,
        "changes": changes,
    }
