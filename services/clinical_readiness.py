"""연구별 데이터 준비도. 승인된 프로토콜이 없으면 임상 판정으로 보지 않는다."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical import ClinicalStudy
from models.clinical_support import (
    ClinicalObservation,
    ClinicalQuery,
    DataLockState,
    DataQualityFinding,
    DataQualityRule,
    QualityEvaluationRun,
    QuestionnaireDefinition,
    QuestionnaireResponse,
    QuestionnaireVersion,
    StudyProtocolDefinition,
    StudySite,
    StudySiteMember,
    StudySubject,
    StudyVisit,
)
from services.clinical_records import (
    ClinicalRecordError,
    _hash,
    _require_site_member,
    _require_study_member,
    get_effective_observation,
)

READINESS_STATUSES = frozenset({
    "COMPLETE",
    "INCOMPLETE",
    "BLOCKED_BY_QUERY",
    "BLOCKED_BY_QUALITY",
    "BLOCKED_PENDING_PROTOCOL",
    "LOCKED",
})
UNRESOLVED_QUERY_STATUSES = frozenset({"open", "answered", "reopened"})
BLOCKING_FINDING_STATUS = "open"
SCOPE_BY_TYPE = {
    "observation": "record",
    "questionnaire_response": "record",
    "visit": "visit",
    "subject": "subject",
    "study": "study",
}
_REQUIREMENT_KEYS = frozenset({
    "required_observations",
    "required_questionnaires",
    "required_visit_codes",
    "blocking_query_severities",
    "blocking_finding_severities",
    "quality_evaluation_required",
    "query_aging_days",
    "recurrent_finding_min",
    "correction_frequency_min",
    "longitudinal_max_abs_delta",
})
_FORBIDDEN = frozenset({
    "treatment_arm",
    "allocation",
    "unblinded",
    "efficacy",
    "name",
    "mrn",
})


@dataclass
class LockContext:
    study_id: str
    scope: str
    target_type: str
    target_id: str
    site_id: str | None
    subject_id: str | None
    visit_id: str | None
    revision: int | None


def resolve_target(session: Session, *, study_id: str, target_type: str, target_id: str) -> LockContext:
    scope = SCOPE_BY_TYPE.get(target_type)
    if scope is None:
        raise ClinicalRecordError("지원하지 않는 잠금 범위입니다.")
    if target_type == "study":
        study = session.get(ClinicalStudy, target_id)
        if study is None or study.id != study_id:
            raise ClinicalRecordError("연구가 없습니다.")
        return LockContext(study_id, scope, target_type, target_id, None, None, None, None)
    if target_type == "subject":
        subject = session.get(StudySubject, target_id)
        if subject is None or subject.study_id != study_id:
            raise ClinicalRecordError("대상자가 없습니다.")
        return LockContext(
            study_id, scope, target_type, target_id, subject.site_id, subject.id, None, None,
        )
    if target_type == "visit":
        visit = session.get(StudyVisit, target_id)
        if visit is None or visit.subject.study_id != study_id:
            raise ClinicalRecordError("Visit 가 없습니다.")
        return LockContext(
            study_id, scope, target_type, target_id, visit.subject.site_id,
            visit.subject_id, visit.id, None,
        )
    if target_type == "observation":
        row = session.get(ClinicalObservation, target_id)
        if row is None or row.visit.subject.study_id != study_id:
            raise ClinicalRecordError("관찰이 없습니다.")
        return LockContext(
            study_id, scope, target_type, target_id, row.visit.subject.site_id,
            row.visit.subject_id, row.visit_id, row.revision,
        )
    response = session.get(QuestionnaireResponse, target_id)
    if response is None or response.visit.subject.study_id != study_id:
        raise ClinicalRecordError("설문 응답이 없습니다.")
    return LockContext(
        study_id, scope, target_type, target_id, response.visit.subject.site_id,
        response.visit.subject_id, response.visit_id, None,
    )


def register_protocol_definition(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    requirements: dict,
) -> StudyProtocolDefinition:
    _require_study_member(session, study_id, actor_user_id)
    _validate_requirements(requirements)
    current = session.scalar(
        select(func.max(StudyProtocolDefinition.version_number)).where(
            StudyProtocolDefinition.study_id == study_id,
        )
    )
    raw = json.dumps(requirements, sort_keys=True, ensure_ascii=False)
    row = StudyProtocolDefinition(
        study_id=study_id,
        version_number=int(current or 0) + 1,
        status="draft",
        requirements_json=raw,
        content_hash=_hash(requirements),
        created_by=actor_user_id,
    )
    session.add(row)
    session.flush()
    return row


def approve_protocol_definition(
    session: Session,
    definition_id: str,
    *,
    actor_user_id: str,
) -> StudyProtocolDefinition:
    row = session.get(StudyProtocolDefinition, definition_id)
    if row is None:
        raise ClinicalRecordError("프로토콜 정의가 없습니다.")
    _require_role(session, row.study_id, actor_user_id, frozenset({"data_manager"}))
    if row.status != "draft":
        raise ClinicalRecordError("초안 프로토콜만 승인할 수 있습니다.")
    row.status = "approved"
    row.approved_by = actor_user_id
    row.approved_at = datetime.now(timezone.utc)
    session.flush()
    return row


def latest_approved_protocol(session: Session, study_id: str) -> StudyProtocolDefinition | None:
    return session.scalar(
        select(StudyProtocolDefinition)
        .where(
            StudyProtocolDefinition.study_id == study_id,
            StudyProtocolDefinition.status == "approved",
        )
        .order_by(StudyProtocolDefinition.version_number.desc())
        .limit(1)
    )


def evaluate_readiness(
    session: Session,
    *,
    study_id: str,
    target_type: str,
    target_id: str,
) -> dict:
    context = resolve_target(session, study_id=study_id, target_type=target_type, target_id=target_id)
    protocol = latest_approved_protocol(session, study_id)
    state = session.scalar(
        select(DataLockState).where(
            DataLockState.study_id == study_id,
            DataLockState.target_type == target_type,
            DataLockState.target_id == target_id,
        )
    )
    lock_state = "DRAFT" if state is None else state.state
    if protocol is None:
        return _report(
            context, lock_state, "BLOCKED_PENDING_PROTOCOL", "NOT_ASSESSED",
            {"protocol": "missing"}, _empty_checks(False), False,
        )
    requirements = json.loads(protocol.requirements_json)
    checks, failures = _checks(session, context, requirements)
    status = _classify(lock_state, checks)
    eligible = status == "COMPLETE" and lock_state == "READY_FOR_REVIEW"
    return _report(
        context, lock_state, status, "OPERATIONAL_NOT_CLINICALLY_VALIDATED",
        {"protocol": "approved", "id": protocol.id, "version_number": protocol.version_number},
        checks, eligible, failures,
    )


def _report(
    context: LockContext,
    lock_state: str,
    status: str,
    assessment_class: str,
    protocol: dict,
    checks: dict,
    lock_eligible: bool,
    failures: list[str] | None = None,
) -> dict:
    if status not in READINESS_STATUSES:
        raise ClinicalRecordError("준비도 상태가 올바르지 않습니다.")
    return {
        "status": status,
        "assessment_class": assessment_class,
        "clinically_validated": False,
        "scope": context.scope,
        "target_type": context.target_type,
        "target_id": context.target_id,
        "study_id": context.study_id,
        "site_id": context.site_id,
        "lock_state": lock_state,
        "lock_eligible": lock_eligible,
        "protocol": protocol,
        "checks": checks,
        "failures": sorted(failures or []),
    }


def _empty_checks(evaluated: bool) -> dict:
    return {
        "required_records_present": False,
        "required_questionnaires_present": False,
        "required_observations_final": False,
        "outstanding_blocking_queries": 0,
        "outstanding_blocking_findings": 0,
        "visit_completion": False,
        "quality_evaluated": evaluated,
    }


def _classify(lock_state: str, checks: dict) -> str:
    if lock_state in {"LOCKED", "UNLOCK_REQUESTED"}:
        return "LOCKED"
    if checks["outstanding_blocking_queries"]:
        return "BLOCKED_BY_QUERY"
    if checks["outstanding_blocking_findings"] or not checks["quality_evaluated"]:
        return "BLOCKED_BY_QUALITY"
    if not (
        checks["required_records_present"]
        and checks["required_questionnaires_present"]
        and checks["required_observations_final"]
        and checks["visit_completion"]
    ):
        return "INCOMPLETE"
    return "COMPLETE"


def _checks(session: Session, context: LockContext, requirements: dict) -> tuple[dict, list[str]]:
    failures: list[str] = []
    visits = _visits_in_scope(session, context)
    missing_records, unfinalized = _observation_gaps(session, context, visits, requirements)
    missing_forms = _questionnaire_gaps(session, context, visits, requirements)
    visit_incomplete = _visit_gaps(session, context, requirements)
    queries = _blocking_queries(session, context, requirements)
    findings = _blocking_findings(session, context, requirements)
    evaluated = _quality_evaluated(session, context, requirements)
    if missing_records:
        failures.extend(f"missing_record:{code}" for code in missing_records)
    if unfinalized:
        failures.extend(f"unfinalized:{code}" for code in unfinalized)
    if missing_forms:
        failures.extend(f"missing_questionnaire:{code}" for code in missing_forms)
    if visit_incomplete:
        failures.extend(f"visit_incomplete:{code}" for code in visit_incomplete)
    if queries:
        failures.append(f"blocking_queries:{len(queries)}")
    if findings:
        failures.append(f"blocking_findings:{len(findings)}")
    if not evaluated:
        failures.append("quality_not_evaluated")
    checks = {
        "required_records_present": not missing_records and not unfinalized,
        "required_questionnaires_present": not missing_forms,
        "required_observations_final": not unfinalized,
        "outstanding_blocking_queries": len(queries),
        "outstanding_blocking_findings": len(findings),
        "visit_completion": not visit_incomplete,
        "quality_evaluated": evaluated,
    }
    return checks, failures


def _visits_in_scope(session: Session, context: LockContext) -> list[StudyVisit]:
    if context.scope == "study":
        return list(session.scalars(
            select(StudyVisit).join(StudyVisit.subject).where(StudyVisit.subject.has(study_id=context.study_id))
        ).all())
    if context.scope == "subject":
        return list(session.scalars(
            select(StudyVisit).where(StudyVisit.subject_id == context.subject_id)
        ).all())
    if context.visit_id:
        visit = session.get(StudyVisit, context.visit_id)
        return [] if visit is None else [visit]
    return []


def _observation_gaps(
    session: Session, context: LockContext, visits: list[StudyVisit], requirements: dict,
) -> tuple[list[str], list[str]]:
    required = requirements.get("required_observations") or []
    if context.target_type == "observation":
        row = session.get(ClinicalObservation, context.target_id)
        if row is None or row.record_status != "final":
            return ["target"], ["target"]
        return [], []
    if context.target_type == "questionnaire_response":
        return [], []
    missing: list[str] = []
    unfinalized: list[str] = []
    for visit in visits:
        for spec in required:
            code = str(spec["code"])
            effective = get_effective_observation(
                session, visit_id=visit.id, code=code,
                laterality=str(spec.get("laterality", "NA")),
                method=str(spec.get("method", "NA")),
                repeat_index=int(spec.get("repeat_index", 1)),
            )
            if effective is None:
                missing.append(code)
                draft = session.scalar(
                    select(ClinicalObservation.id).where(
                        ClinicalObservation.visit_id == visit.id,
                        ClinicalObservation.code == code,
                        ClinicalObservation.record_status == "draft",
                    )
                )
                if draft is not None:
                    unfinalized.append(code)
    return sorted(set(missing)), sorted(set(unfinalized))


def _questionnaire_gaps(
    session: Session, context: LockContext, visits: list[StudyVisit], requirements: dict,
) -> list[str]:
    required = [str(item["definition_code"]) for item in requirements.get("required_questionnaires") or []]
    if context.target_type == "questionnaire_response":
        response = session.get(QuestionnaireResponse, context.target_id)
        if response is None or response.status != "final":
            return ["target"]
        return []
    if context.scope == "record":
        return []
    missing: list[str] = []
    for code in required:
        definition = session.scalar(
            select(QuestionnaireDefinition).where(
                QuestionnaireDefinition.study_id == context.study_id,
                QuestionnaireDefinition.code == code,
            )
        )
        if definition is None:
            missing.append(code)
            continue
        for visit in visits:
            found = session.scalar(
                select(QuestionnaireResponse.id)
                .join(QuestionnaireVersion, QuestionnaireVersion.id == QuestionnaireResponse.version_id)
                .where(
                    QuestionnaireResponse.visit_id == visit.id,
                    QuestionnaireResponse.status == "final",
                    QuestionnaireVersion.definition_id == definition.id,
                )
            )
            if found is None:
                missing.append(code)
    return sorted(set(missing))


def _visit_gaps(session: Session, context: LockContext, requirements: dict) -> list[str]:
    required = [str(code) for code in requirements.get("required_visit_codes") or []]
    if context.scope in {"record", "visit"} or not required:
        return []
    subjects = _subjects_in_scope(session, context)
    missing: list[str] = []
    for subject in subjects:
        present = set(session.scalars(
            select(StudyVisit.visit_code).where(StudyVisit.subject_id == subject.id)
        ).all())
        missing.extend(code for code in required if code not in present)
    return sorted(set(missing))


def _subjects_in_scope(session: Session, context: LockContext) -> list[StudySubject]:
    if context.scope == "study":
        return list(session.scalars(
            select(StudySubject).where(StudySubject.study_id == context.study_id)
        ).all())
    if context.subject_id:
        subject = session.get(StudySubject, context.subject_id)
        return [] if subject is None else [subject]
    return []


def _blocking_queries(session: Session, context: LockContext, requirements: dict) -> list[ClinicalQuery]:
    severities = set(requirements.get("blocking_query_severities") or ["error", "critical"])
    rows = list(session.scalars(
        select(ClinicalQuery).where(
            ClinicalQuery.study_id == context.study_id,
            ClinicalQuery.status.in_(tuple(UNRESOLVED_QUERY_STATUSES)),
            ClinicalQuery.severity.in_(tuple(severities)),
        )
    ).all())
    return [row for row in rows if _query_in_scope(session, row, context)]


def _query_in_scope(session: Session, query: ClinicalQuery, context: LockContext) -> bool:
    if context.scope == "study":
        return True
    if query.finding_id and not query.observation_id:
        finding = session.get(DataQualityFinding, query.finding_id)
        if finding is not None and finding.target_type == "observation":
            query_observation = session.get(ClinicalObservation, finding.target_id)
            if query_observation is not None and context.target_type == "observation":
                if context.target_id == query_observation.id:
                    return True
            if query_observation is not None:
                return _same_branch(
                    context,
                    query_observation.visit.subject.site_id,
                    query_observation.visit.subject_id,
                    query_observation.visit_id,
                )
    if query.observation_id:
        if context.target_type == "observation" and context.target_id == query.observation_id:
            return True
        observation = session.get(ClinicalObservation, query.observation_id)
        if observation is None:
            return False
        return _same_branch(
            context, observation.visit.subject.site_id, observation.visit.subject_id, observation.visit_id,
        )
    if query.visit_id:
        visit = session.get(StudyVisit, query.visit_id)
        if visit is None:
            return False
        if context.scope == "record":
            return context.visit_id == visit.id
        return _same_branch(context, visit.subject.site_id, visit.subject_id, visit.id)
    if query.subject_id:
        if context.scope == "record" or context.target_type == "visit":
            return context.subject_id == query.subject_id
        return context.subject_id == query.subject_id or context.scope == "study"
    return context.scope == "study"


def _same_branch(context: LockContext, site_id: str, subject_id: str, visit_id: str) -> bool:
    if context.scope == "visit":
        return context.visit_id == visit_id
    if context.scope == "subject":
        return context.subject_id == subject_id
    if context.scope == "record":
        return context.visit_id == visit_id
    return context.site_id == site_id


def _blocking_findings(session: Session, context: LockContext, requirements: dict) -> list[DataQualityFinding]:
    severities = set(requirements.get("blocking_finding_severities") or ["error", "critical"])
    rows = list(session.scalars(
        select(DataQualityFinding)
        .join(DataQualityRule, DataQualityRule.id == DataQualityFinding.rule_id)
        .where(
            DataQualityFinding.study_id == context.study_id,
            DataQualityFinding.status == BLOCKING_FINDING_STATUS,
            DataQualityRule.severity.in_(tuple(severities)),
        )
    ).all())
    return [row for row in rows if _finding_in_scope(session, row, context)]


def _finding_in_scope(session: Session, finding: DataQualityFinding, context: LockContext) -> bool:
    if context.scope == "study":
        return True
    if finding.target_type == "observation":
        if context.target_type == "observation" and context.target_id == finding.target_id:
            return True
        observation = session.get(ClinicalObservation, finding.target_id)
        if observation is None:
            return False
        return _same_branch(
            context, observation.visit.subject.site_id, observation.visit.subject_id, observation.visit_id,
        )
    if finding.visit_id:
        if context.scope == "record":
            return context.visit_id == finding.visit_id
        if context.target_type == "visit":
            return context.target_id == finding.visit_id
        return context.subject_id == finding.subject_id
    if finding.subject_id:
        return context.subject_id == finding.subject_id
    return False


def _quality_evaluated(session: Session, context: LockContext, requirements: dict) -> bool:
    if requirements.get("quality_evaluation_required") is False:
        return True
    active = session.scalar(
        select(func.count()).select_from(DataQualityRule).where(
            DataQualityRule.study_id == context.study_id,
            DataQualityRule.status == "active",
        )
    ) or 0
    if int(active) == 0:
        return True
    runs = list(session.scalars(
        select(QualityEvaluationRun).where(
            QualityEvaluationRun.study_id == context.study_id,
            QualityEvaluationRun.status == "completed",
        )
    ).all())
    for run in runs:
        if run.scope == "study":
            return True
        if context.scope == "study":
            continue
        if run.scope == "subject" and run.scope_id == context.subject_id:
            return True
        if run.scope == "visit" and context.visit_id and run.scope_id == context.visit_id:
            return True
    return False


def _require_role(session: Session, study_id: str, user_id: str, roles: frozenset[str]) -> None:
    _require_study_member(session, study_id, user_id)
    found = session.scalar(
        select(StudySiteMember.role)
        .join(StudySite, StudySite.id == StudySiteMember.site_id)
        .where(
            StudySite.study_id == study_id,
            StudySiteMember.user_id == user_id,
            StudySiteMember.role.in_(tuple(roles)),
        )
    )
    if found is None:
        raise ClinicalRecordError("프로토콜 승인 권한이 없습니다.")


def _validate_requirements(requirements: dict) -> None:
    if not isinstance(requirements, dict):
        raise ClinicalRecordError("프로토콜 요구사항은 객체여야 합니다.")
    unknown = set(requirements) - _REQUIREMENT_KEYS
    if unknown:
        raise ClinicalRecordError("지원하지 않는 프로토콜 항목입니다.")
    _reject_forbidden(requirements, allow_delta=False)
    for spec in requirements.get("required_observations") or []:
        if not isinstance(spec, dict) or not str(spec.get("code", "")).strip():
            raise ClinicalRecordError("필수 관찰 코드가 필요합니다.")
    for spec in requirements.get("required_questionnaires") or []:
        if not isinstance(spec, dict) or not str(spec.get("definition_code", "")).strip():
            raise ClinicalRecordError("필수 설문 코드가 필요합니다.")
    for key in ("query_aging_days", "recurrent_finding_min", "correction_frequency_min"):
        if key in requirements and (not isinstance(requirements[key], int) or requirements[key] < 1):
            raise ClinicalRecordError("모니터링 기준은 양의 정수여야 합니다.")
    delta = requirements.get("longitudinal_max_abs_delta")
    if delta is not None and not isinstance(delta, dict):
        raise ClinicalRecordError("종단 비교 기준은 연구 정의 객체여야 합니다.")


def _reject_forbidden(value, *, allow_delta: bool) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _FORBIDDEN or key in {"min", "max", "threshold"}:
                if not (allow_delta and key == "longitudinal_max_abs_delta"):
                    if key in {"min", "max", "threshold"} or key in _FORBIDDEN:
                        raise ClinicalRecordError("확인되지 않은 임상 임계값이나 치료 정보는 등록하지 않습니다.")
            child_allow = allow_delta or key == "longitudinal_max_abs_delta"
            if key == "longitudinal_max_abs_delta":
                continue
            _reject_forbidden(item, allow_delta=child_allow)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden(item, allow_delta=allow_delta)


def require_readable_member(session: Session, context: LockContext, user_id: str):
    if context.scope == "study" or context.site_id is None:
        _require_study_member(session, context.study_id, user_id)
        return None
    return _require_site_member(session, context.site_id, user_id)
