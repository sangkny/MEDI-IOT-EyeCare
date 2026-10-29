"""개발용 개선 제안 레지스트리. 임상 운영 DB를 자동으로 고치지 않는다."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.clinical_support import ImprovementFinding
from services.clinical_records import ClinicalRecordError

TRANSITIONS = {
    "DETECTED": {"TRIAGED"},
    "TRIAGED": {"ACCEPTED", "REJECTED"},
    "ACCEPTED": {"IMPLEMENTED"},
    "REJECTED": {"CLOSED"},
    "IMPLEMENTED": {"RETESTED"},
    "RETESTED": {"CLOSED"},
}


def record_finding(
    session: Session,
    *,
    finding_code: str,
    source_analyzer: str,
    source_version: str,
    module_id: str,
    severity: str,
    evidence: dict,
    proposed_correction: str,
    reproduction: str | None = None,
) -> ImprovementFinding:
    exists = session.scalar(
        select(ImprovementFinding).where(ImprovementFinding.finding_code == finding_code)
    )
    if exists is not None:
        raise ClinicalRecordError("이미 있는 개선 제안입니다.")
    row = ImprovementFinding(
        finding_code=finding_code,
        source_analyzer=source_analyzer,
        source_version=source_version,
        module_id=module_id,
        severity=severity,
        evidence_json=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        proposed_correction=proposed_correction,
        reproduction=reproduction,
        state="DETECTED",
    )
    session.add(row)
    session.flush()
    return row


def transition_finding(
    session: Session,
    finding_id: str,
    *,
    next_state: str,
    decision: str | None = None,
    decision_reason: str | None = None,
    fix_ref: str | None = None,
    test_evidence: str | None = None,
    reanalysis_outcome: str | None = None,
) -> ImprovementFinding:
    row = session.get(ImprovementFinding, finding_id)
    if row is None:
        raise ClinicalRecordError("개선 제안이 없습니다.")
    allowed = TRANSITIONS.get(row.state, set())
    if next_state not in allowed:
        raise ClinicalRecordError(f"{row.state} 에서 {next_state} 로 갈 수 없습니다.")
    if next_state == "CLOSED":
        if row.state == "REJECTED":
            if not (decision_reason or row.decision_reason):
                raise ClinicalRecordError("거절 종료에는 사유가 필요합니다.")
        elif not (test_evidence or row.test_evidence):
            raise ClinicalRecordError("종료에는 검증 증거가 필요합니다.")
    if next_state in {"ACCEPTED", "REJECTED"}:
        row.decision = decision or next_state
        row.decision_reason = decision_reason
    if fix_ref:
        row.fix_ref = fix_ref
    if test_evidence:
        row.test_evidence = test_evidence
    if reanalysis_outcome:
        row.reanalysis_outcome = reanalysis_outcome
    row.state = next_state
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return row


def list_findings(session: Session) -> list[ImprovementFinding]:
    return list(session.scalars(select(ImprovementFinding).order_by(ImprovementFinding.created_at)))
