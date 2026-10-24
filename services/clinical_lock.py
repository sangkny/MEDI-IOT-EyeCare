"""임상 데이터 잠금과 통제된 해제.

서비스 함수는 사이트 역할과 상태 전이를 직접 검사한다.
호출자가 역할 문자열을 넘겨 권한을 넓힐 수 없다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.clinical_support import (
    ClinicalAuditEvent,
    DataLockRecord,
    DataLockState,
    DataUnlockRequest,
    StudySite,
    StudySiteMember,
)
from services.clinical_readiness import (
    LockContext,
    evaluate_readiness,
    require_readable_member,
    resolve_target,
)
from services.clinical_records import (
    ClinicalRecordError,
    _audit,
    _require_site_member,
    _require_study_member,
)

LOCK_TRANSITIONS = {
    "DRAFT": frozenset({"READY_FOR_REVIEW"}),
    "READY_FOR_REVIEW": frozenset({"LOCKED"}),
    "LOCKED": frozenset({"UNLOCK_REQUESTED"}),
    "UNLOCK_REQUESTED": frozenset({"UNLOCKED", "LOCKED"}),
    "UNLOCKED": frozenset({"READY_FOR_REVIEW"}),
}
LOCK_REQUEST_ROLES = frozenset({"investigator", "data_manager"})
LOCK_APPLY_ROLES = frozenset({"data_manager"})
UNLOCK_REQUEST_ROLES = frozenset({"investigator", "data_manager"})
UNLOCK_DECIDE_ROLES = frozenset({"data_manager"})


def evaluate_lock_readiness(
    session: Session,
    *,
    study_id: str,
    target_type: str,
    target_id: str,
    actor_user_id: str,
) -> dict:
    context = resolve_target(
        session, study_id=study_id, target_type=target_type, target_id=target_id,
    )
    require_readable_member(session, context, actor_user_id)
    report = evaluate_readiness(
        session, study_id=study_id, target_type=target_type, target_id=target_id,
    )
    report["actor_authorized_to_apply"] = _has_roles(session, context, actor_user_id, LOCK_APPLY_ROLES)
    report["actor_authorized_to_request_unlock"] = _has_roles(
        session, context, actor_user_id, UNLOCK_REQUEST_ROLES,
    )
    return report


def request_lock(
    session: Session,
    *,
    study_id: str,
    target_type: str,
    target_id: str,
    actor_user_id: str,
    reason: str,
    request_id: str | None = None,
) -> DataLockState:
    _require_text(reason, "잠금 요청 사유가 필요합니다.")
    context = _authorized_context(
        session, study_id, target_type, target_id, actor_user_id, LOCK_REQUEST_ROLES,
    )
    state = _ensure_state(session, context)
    if state.state not in {"DRAFT", "UNLOCKED"}:
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    return _transition(
        session, state, context, actor_user_id, "READY_FOR_REVIEW", reason, request_id, "lock_request",
    )


def apply_lock(
    session: Session,
    *,
    study_id: str,
    target_type: str,
    target_id: str,
    actor_user_id: str,
    reason: str,
    request_id: str | None = None,
) -> DataLockState:
    _require_text(reason, "잠금 사유가 필요합니다.")
    context = _authorized_context(
        session, study_id, target_type, target_id, actor_user_id, LOCK_APPLY_ROLES,
    )
    state = _get_state(session, context)
    if state is None or state.state != "READY_FOR_REVIEW":
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    report = evaluate_readiness(
        session, study_id=study_id, target_type=target_type, target_id=target_id,
    )
    if report["status"] != "COMPLETE":
        raise ClinicalRecordError(f"잠금 조건을 충족하지 않습니다: {report['status']}")
    return _transition(
        session, state, context, actor_user_id, "LOCKED", reason, request_id, "lock_apply",
    )


def request_unlock(
    session: Session,
    *,
    study_id: str,
    target_type: str,
    target_id: str,
    actor_user_id: str,
    reason: str,
    request_id: str | None = None,
) -> DataUnlockRequest:
    _require_text(reason, "해제 요청 사유가 필요합니다.")
    context = _authorized_context(
        session, study_id, target_type, target_id, actor_user_id, UNLOCK_REQUEST_ROLES,
    )
    state = _get_state(session, context)
    if state is None or state.state != "LOCKED":
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    pending = session.scalar(
        select(DataUnlockRequest.id).where(
            DataUnlockRequest.lock_state_id == state.id,
            DataUnlockRequest.status == "pending",
        )
    )
    if pending is not None:
        raise ClinicalRecordError("이미 대기 중인 해제 요청이 있습니다.")
    correlation = request_id or str(uuid.uuid4())
    nested = session.begin_nested()
    try:
        unlock = DataUnlockRequest(
            lock_state_id=state.id,
            study_id=context.study_id,
            site_id=context.site_id,
            target_type=context.target_type,
            target_id=context.target_id,
            lock_state_at_request=state.state,
            requesting_user_id=actor_user_id,
            reason=reason.strip(),
            request_id=correlation,
            status="pending",
            requested_at=datetime.now(timezone.utc),
        )
        session.add(unlock)
        session.flush()
        _transition(
            session, state, context, actor_user_id, "UNLOCK_REQUESTED", reason, correlation,
            "unlock_request", unlock_request_id=unlock.id,
        )
        nested.commit()
    except Exception:
        nested.rollback()
        session.expire_all()
        raise
    session.refresh(unlock)
    return unlock


def approve_unlock(
    session: Session,
    request_row_id: str,
    *,
    actor_user_id: str,
    reason: str,
    request_id: str | None = None,
) -> DataLockState:
    return _decide_unlock(
        session, request_row_id, actor_user_id=actor_user_id, reason=reason,
        request_id=request_id, approved=True,
    )


def reject_unlock(
    session: Session,
    request_row_id: str,
    *,
    actor_user_id: str,
    reason: str,
    request_id: str | None = None,
) -> DataLockState:
    return _decide_unlock(
        session, request_row_id, actor_user_id=actor_user_id, reason=reason,
        request_id=request_id, approved=False,
    )


def list_lock_history(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[DataLockRecord]:
    _require_study_member(session, study_id, actor_user_id)
    if target_type and target_id:
        context = resolve_target(
            session, study_id=study_id, target_type=target_type, target_id=target_id,
        )
        require_readable_member(session, context, actor_user_id)
    visible_sites = set(session.scalars(
        select(StudySiteMember.site_id).where(StudySiteMember.user_id == actor_user_id)
    ).all())
    stmt = select(DataLockRecord).where(DataLockRecord.study_id == study_id)
    if target_type and target_id:
        stmt = stmt.where(
            DataLockRecord.target_type == target_type,
            DataLockRecord.target_id == target_id,
        )
    rows = list(session.scalars(stmt.order_by(DataLockRecord.occurred_at, DataLockRecord.id)).all())
    return [
        row for row in rows
        if row.site_id is None or row.site_id in visible_sites
    ]


def list_clinical_audit(
    session: Session,
    *,
    study_id: str,
    actor_user_id: str,
    target_type: str | None = None,
    target_id: str | None = None,
) -> list[ClinicalAuditEvent]:
    _require_study_member(session, study_id, actor_user_id)
    if target_type and target_id:
        context = resolve_target(
            session, study_id=study_id, target_type=target_type, target_id=target_id,
        )
        require_readable_member(session, context, actor_user_id)
    visible_sites = set(session.scalars(
        select(StudySiteMember.site_id).where(StudySiteMember.user_id == actor_user_id)
    ).all())
    stmt = select(ClinicalAuditEvent).where(ClinicalAuditEvent.study_id == study_id)
    if target_type and target_id:
        stmt = stmt.where(
            ClinicalAuditEvent.target_type == target_type,
            ClinicalAuditEvent.target_id == target_id,
        )
    rows = list(session.scalars(stmt.order_by(ClinicalAuditEvent.occurred_at, ClinicalAuditEvent.id)).all())
    return [
        row for row in rows
        if row.site_id is None or row.site_id in visible_sites
    ]


def _decide_unlock(
    session: Session,
    request_row_id: str,
    *,
    actor_user_id: str,
    reason: str,
    request_id: str | None,
    approved: bool,
) -> DataLockState:
    _require_text(reason, "해제 결정 사유가 필요합니다.")
    unlock = session.get(DataUnlockRequest, request_row_id)
    if unlock is None:
        raise ClinicalRecordError("해제 요청이 없습니다.")
    if unlock.status != "pending":
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    if unlock.requesting_user_id == actor_user_id:
        raise ClinicalRecordError("해제 승인 권한이 없습니다.")
    context = _authorized_context(
        session, unlock.study_id, unlock.target_type, unlock.target_id,
        actor_user_id, UNLOCK_DECIDE_ROLES,
    )
    state = session.get(DataLockState, unlock.lock_state_id)
    if state is None or state.state != "UNLOCK_REQUESTED":
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    unlock.status = "approved" if approved else "rejected"
    unlock.decided_by = actor_user_id
    unlock.decision_reason = reason.strip()
    unlock.decided_at = datetime.now(timezone.utc)
    session.flush()
    destination = "UNLOCKED" if approved else "LOCKED"
    action = "unlock_approve" if approved else "unlock_reject"
    return _transition(
        session, state, context, actor_user_id, destination, reason, request_id or unlock.request_id,
        action, unlock_request_id=unlock.id,
    )


def _transition(
    session: Session,
    state: DataLockState,
    context: LockContext,
    actor_user_id: str,
    to_state: str,
    reason: str,
    request_id: str | None,
    action: str,
    unlock_request_id: str | None = None,
) -> DataLockState:
    allowed = LOCK_TRANSITIONS.get(state.state, frozenset())
    if to_state not in allowed:
        raise ClinicalRecordError("허용되지 않는 잠금 전이입니다.")
    expected = state.version
    from_state = state.state
    correlation = request_id or str(uuid.uuid4())
    nested = session.begin_nested()
    try:
        result = session.execute(
            update(DataLockState)
            .where(
                DataLockState.id == state.id,
                DataLockState.version == expected,
                DataLockState.state == from_state,
            )
            .values(
                state=to_state,
                version=expected + 1,
                target_revision=context.revision,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount not in (1, -1):
            raise ClinicalRecordError("동시 잠금 충돌입니다.")
        if result.rowcount == -1:
            session.expire(state)
            current = session.get(DataLockState, state.id)
            if current is None or current.state != to_state or current.version != expected + 1:
                raise ClinicalRecordError("동시 잠금 충돌입니다.")
        session.add(DataLockRecord(
            study_id=context.study_id,
            site_id=context.site_id,
            lock_state_id=state.id,
            target_type=context.target_type,
            target_id=context.target_id,
            action=action,
            from_state=from_state,
            to_state=to_state,
            state_version=expected,
            reason=reason.strip(),
            actor_user_id=actor_user_id,
            request_id=correlation,
            target_revision=context.revision,
            unlock_request_id=unlock_request_id,
            occurred_at=datetime.now(timezone.utc),
        ))
        _audit(
            session,
            study_id=context.study_id,
            site_id=context.site_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=context.target_type,
            target_id=context.target_id,
            request_id=correlation,
            previous_state=from_state,
            new_state=to_state,
            reason=reason.strip(),
            target_revision=context.revision,
            payload={
                "scope": context.scope,
                "previous_state": from_state,
                "new_state": to_state,
                "reason": reason.strip(),
                "target_revision": context.revision,
                "request_id": correlation,
                "state_version": expected,
            },
        )
        session.flush()
        nested.commit()
    except IntegrityError as exc:
        nested.rollback()
        session.expire_all()
        raise ClinicalRecordError("동시 잠금 충돌입니다.") from exc
    except Exception:
        nested.rollback()
        session.expire_all()
        raise
    session.expire(state)
    session.refresh(state)
    return state


def _ensure_state(session: Session, context: LockContext) -> DataLockState:
    existing = _get_state(session, context)
    if existing is not None:
        return existing
    row = DataLockState(
        study_id=context.study_id,
        site_id=context.site_id,
        scope=context.scope,
        target_type=context.target_type,
        target_id=context.target_id,
        state="DRAFT",
        version=1,
        target_revision=context.revision,
        updated_at=datetime.now(timezone.utc),
    )
    nested = session.begin_nested()
    try:
        session.add(row)
        session.flush()
        nested.commit()
    except IntegrityError:
        nested.rollback()
        session.expire_all()
        existing = _get_state(session, context)
        if existing is None:
            raise ClinicalRecordError("동시 잠금 충돌입니다.") from None
        return existing
    return row


def _get_state(session: Session, context: LockContext) -> DataLockState | None:
    return session.scalar(
        select(DataLockState).where(
            DataLockState.study_id == context.study_id,
            DataLockState.target_type == context.target_type,
            DataLockState.target_id == context.target_id,
        )
    )


def _authorized_context(
    session: Session,
    study_id: str,
    target_type: str,
    target_id: str,
    actor_user_id: str,
    roles: frozenset[str],
) -> LockContext:
    context = resolve_target(
        session, study_id=study_id, target_type=target_type, target_id=target_id,
    )
    if not _has_roles(session, context, actor_user_id, roles):
        if context.site_id is None:
            _require_study_member(session, context.study_id, actor_user_id)
        else:
            _require_site_member(session, context.site_id, actor_user_id)
        raise ClinicalRecordError("잠금 권한이 없습니다.")
    return context


def _has_roles(
    session: Session, context: LockContext, user_id: str, roles: frozenset[str],
) -> bool:
    if context.scope == "study" or context.site_id is None:
        sites = list(session.scalars(select(StudySite).where(StudySite.study_id == context.study_id)).all())
        if not sites:
            return False
        for site in sites:
            member = session.scalar(
                select(StudySiteMember).where(
                    StudySiteMember.site_id == site.id,
                    StudySiteMember.user_id == user_id,
                )
            )
            if member is None or member.role not in roles:
                return False
        return True
    member = session.scalar(
        select(StudySiteMember).where(
            StudySiteMember.site_id == context.site_id,
            StudySiteMember.user_id == user_id,
        )
    )
    return member is not None and member.role in roles


def _require_text(value: str, message: str) -> None:
    if not value or not str(value).strip():
        raise ClinicalRecordError(message)
