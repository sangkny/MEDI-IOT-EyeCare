"""Phase 014 Clinical Operations UI — 페이지와 세션/감사 enrichment."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from auth.policy import policy_require
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.clinical_support import AuditEventChain, ClinicalAuditEvent, StudySiteMember
from services.clinical_lock import list_clinical_audit
from services.clinical_records import ClinicalRecordError, list_authorized_studies, list_sites_for_member, verify_audit_integrity

router = APIRouter()
page_router = APIRouter()
_STATIC = Path(__file__).resolve().parent.parent / "static" / "clinical-ops"


def _fail(exc: ClinicalRecordError) -> HTTPException:
    text = str(exc)
    if "구성원" in text or "권한" in text:
        code = status.HTTP_403_FORBIDDEN
    elif any(token in text for token in ("가 없습니다", "이 없습니다", "은 없습니다", "에 없습니다")):
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=text)


async def _call(db: AsyncSession, fn, **kwargs):
    try:
        return await db.run_sync(lambda sync: fn(sync, **kwargs))
    except ClinicalRecordError as exc:
        raise _fail(exc) from exc


def _uid(user: dict) -> str:
    return str(user["user_id"])


def _role(user: dict) -> str:
    return str(user.get("role") or "unknown")


@page_router.get("/clinical-ops")
@page_router.get("/clinical-ops/")
async def clinical_ops_index() -> FileResponse:
    page = _STATIC / "index.html"
    if not page.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Clinical Operations UI가 없습니다.")
    return FileResponse(page, media_type="text/html; charset=utf-8")


@page_router.get("/clinical-ops/{asset_path:path}")
async def clinical_ops_asset(asset_path: str) -> FileResponse:
    if ".." in asset_path or asset_path.startswith("/") or "\\" in asset_path:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="잘못된 경로입니다.")
    target = (_STATIC / asset_path).resolve()
    if not str(target).startswith(str(_STATIC.resolve())) or not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="자원을 찾을 수 없습니다.")
    media = None
    if target.suffix == ".css":
        media = "text/css; charset=utf-8"
    elif target.suffix == ".html":
        media = "text/html; charset=utf-8"
    elif target.suffix == ".js":
        media = "text/javascript; charset=utf-8"
    return FileResponse(target, media_type=media)


@router.get("/ops/session")
async def ops_session(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_study_read")),
) -> dict:
    """로그인 직후 역할·허용 연구/사이트 범위를 반환한다. 토큰/비밀번호는 포함하지 않는다."""
    user_id = _uid(user)
    role = _role(user)
    studies = await _call(db, list_authorized_studies, user_id=user_id)

    def _sites(sync, study_id: str):
        return list_sites_for_member(sync, study_id=study_id, user_id=user_id)

    study_payload = []
    for study in studies:
        sites = await _call(db, _sites, study_id=study.id)
        study_payload.append({
            "id": study.id,
            "code": study.code,
            "name": study.name,
            "study_kind": getattr(study, "study_kind", None),
            "protocol_version": getattr(study, "protocol_version", None),
            "sites": [
                {"id": site.id, "site_code": site.site_code, "name": site.name}
                for site in sites
            ],
        })
    return {
        "user_id": user_id,
        "role": role,
        "nav": _nav_for_role(role),
        "studies": study_payload,
    }


def _nav_for_role(role: str) -> list[str]:
    base = ["dashboard", "subjects", "ecrf", "questionnaires", "queries", "protocol"]
    if role in {"doctor", "staff", "crc", "investigator", "manager", "dm", "data_manager", "admin"}:
        base = ["dashboard", "subjects", "ecrf", "questionnaires", "queries", "locks", "audit", "protocol"]
    if role in {"viewer"}:
        base = ["dashboard", "subjects", "protocol"]
    return base


def _enrich_audit_rows(sync, rows: list[ClinicalAuditEvent]) -> list[dict]:
    event_ids = [row.id for row in rows]
    chains = {}
    if event_ids:
        for chain in sync.scalars(
            select(AuditEventChain).where(AuditEventChain.event_id.in_(event_ids))
        ).all():
            chains[chain.event_id] = chain
    payload = []
    for row in rows:
        chain = chains.get(row.id)
        integrity = verify_audit_integrity(row)
        if chain is not None:
            integrity_label = "HASH_CHAINED"
            if integrity.get("status") == "MISMATCH":
                integrity_label = "HASH_CHAINED_PAYLOAD_MISMATCH"
        elif integrity.get("status") == "LEGACY_HASH_ONLY":
            integrity_label = "LEGACY_HASH_ONLY"
        else:
            integrity_label = "EVENT_HASH_ONLY"
        payload.append({
            "id": row.id,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
            "actor_user_id": row.actor_user_id,
            "actor_role": chain.actor_role if chain else None,
            "action": row.action,
            "event_type": row.action,
            "study_id": row.study_id,
            "site_id": row.site_id,
            "subject_id": None,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_revision": row.target_revision,
            "reason": row.reason,
            "correlation_id": chain.correlation_id if chain else row.request_id,
            "request_id": row.request_id,
            "integrity_status": integrity_label,
            "integrity_detail": integrity.get("status"),
            "chain_seq": chain.chain_seq if chain else None,
            "protocol_version": chain.protocol_version if chain else None,
            "previous_state": row.previous_state,
            "new_state": row.new_state,
            # Never return payload_json / credentials / protected values.
        })
    return payload


@router.get("/ops/audits")
async def ops_audits(
    study_id: str,
    site_id: str | None = None,
    subject_id: str | None = None,
    action: str | None = None,
    event_category: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(policy_require("medi-iot", "clinical_audit_read")),
) -> list[dict]:
    """읽기 전용 감사 조회. 해시 체인 여부는 사건별로만 표시한다."""
    rows = await _call(
        db, list_clinical_audit, study_id=study_id, actor_user_id=_uid(user),
        target_type=target_type, target_id=target_id,
    )
    category = (event_category or action or "").strip().lower()

    def _filter(sync):
        filtered = []
        for row in rows:
            if site_id and row.site_id and row.site_id != site_id:
                continue
            if site_id and row.site_id is None:
                # study-level events remain visible when site filter set
                pass
            if category and category not in (row.action or "").lower():
                continue
            if date_from and row.occurred_at and row.occurred_at < date_from:
                continue
            if date_to and row.occurred_at and row.occurred_at > date_to:
                continue
            if subject_id:
                # subject scoping: only when target is subject or visit linked — best-effort via target_id match
                if row.target_type == "subject" and row.target_id != subject_id:
                    continue
            filtered.append(row)
        # site membership already enforced in list_clinical_audit
        _ = sync.scalars(
            select(StudySiteMember.id).where(StudySiteMember.user_id == _uid(user)).limit(1)
        ).first()
        return _enrich_audit_rows(sync, filtered)

    return await db.run_sync(_filter)
