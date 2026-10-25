"""외부 표 반출을 정규 임상 엔티티로 가져온다.

미리보기는 저장하지 않는다. 확정은 한 트랜잭션이며 같은 해시는 다시 쓰지 않는다.
값이 다른 개정 파일은 기존 관찰을 덮어쓰지 않고 불일치로 남긴다.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.clinical_support import (
    ImportBatch,
    ImportDiscrepancy,
    ImportLink,
    ImportSource,
    ImportStagingRow,
    ImportValidationFinding,
    QuestionnaireDefinition,
    QuestionnaireVersion,
    StudySite,
    StudySubject,
    StudyVisit,
)
from services.clinical_import_checks import evaluate_row, parse_number
from services.clinical_import_parse import (
    ADAPTER_NAME,
    MAPPING_VERSION,
    ItemSpec,
    ParsedRow,
    ParsedSheet,
    ParsedWorkbook,
    parse_workbook,
)
from services.clinical_records import (
    ClinicalRecordError,
    _audit,
    _require_site_member,
    create_draft_observation,
    define_questionnaire,
    enroll_subject,
    open_visit,
    publish_questionnaire_version,
    save_response_item,
    start_response,
)

_TBUT_REPEAT = re.compile(r"TB(OD|OS)ORS([123])$")
_TBUT_AVERAGE = re.compile(r"TB(OD|OS)ORSAV$")
_SCHIRMER = re.compile(r"ST(OD|OS)ORS$")
_SCHIRMER_NASAL = re.compile(r"ST(OD|OS)NORS$")
_OSDI_ITEM = re.compile(r"OSQ(\d+)$")


def _basename(filename: str) -> str:
    name = Path(filename).name.strip()
    if not name or name in {".", ".."}:
        raise ClinicalRecordError("파일 이름이 없습니다.")
    return name[:255]


def _parse_date(value: object) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ClinicalRecordError("UNPARSED_VISIT_DATE")


def _subject_code(value: object) -> str | None:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _eye(token: str) -> str:
    return "OD" if token == "OD" else "OS"


def canonical_target(item: ItemSpec) -> dict | None:
    if item.blinded or item.sensitive:
        return None
    item_id = item.item_id
    if (match := _TBUT_REPEAT.fullmatch(item_id)):
        return {"kind": "observation", "code": "TBUT", "laterality": _eye(match.group(1)), "repeat": int(match.group(2)), "method": "repeat"}
    if (match := _TBUT_AVERAGE.fullmatch(item_id)):
        return {"kind": "observation", "code": "TBUT", "laterality": _eye(match.group(1)), "repeat": 0, "method": "reported_average"}
    if (match := _SCHIRMER.fullmatch(item_id)):
        return {"kind": "observation", "code": "SCHIRMER", "laterality": _eye(match.group(1)), "repeat": 1, "method": "standard"}
    if (match := _SCHIRMER_NASAL.fullmatch(item_id)):
        return {"kind": "observation", "code": "SCHIRMER_NASAL", "laterality": _eye(match.group(1)), "repeat": 1, "method": "nasal"}
    if item_id == "OSSCORE":
        return {"kind": "observation", "code": "OSDI_SCORE", "laterality": "NA", "repeat": 1, "method": "score"}
    if (match := _OSDI_ITEM.fullmatch(item_id)):
        return {"kind": "questionnaire", "code": "OSDI", "item_code": item_id, "repeat": int(match.group(1))}
    return None


def _value_sha(item_id: str, value: object) -> str:
    payload = {"item_id": item_id, "value": value}
    return __import__("hashlib").sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _summary_from_workbook(parsed: ParsedWorkbook) -> dict:
    confirmed = [sheet for sheet in parsed.sheets if sheet.alignment == "confirmed"]
    unresolved = [sheet for sheet in parsed.sheets if sheet.alignment != "confirmed"]
    mapped: set[str] = set()
    unmapped: set[str] = set()
    for sheet in confirmed:
        for item in sheet.items:
            if canonical_target(item) is None and item.item_id not in {"SUBJID", "SVDAT"}:
                unmapped.add(item.item_id)
            elif canonical_target(item) is not None:
                mapped.add(item.item_id)
    return {
        "adapter": ADAPTER_NAME,
        "mapping_version": MAPPING_VERSION,
        "content_sha256": parsed.content_sha256,
        "byte_size": parsed.byte_size,
        "sheet_count": len(parsed.sheets),
        "confirmed_sheet_count": len(confirmed),
        "unresolved_sheet_count": len(unresolved),
        "data_row_count": parsed.data_row_count,
        "mapped_item_ids": sorted(mapped),
        "unmapped_item_count": len(unmapped),
        "persisted": False,
    }


def preview_import(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    content: bytes,
) -> dict:
    _require_import_scope(session, study_id, site_id, actor_user_id)
    return _summary_from_workbook(parse_workbook(content))


def _require_import_scope(session: Session, study_id: str, site_id: str, actor_user_id: str) -> None:
    site = session.get(StudySite, site_id)
    if site is None or site.study_id != study_id:
        raise ClinicalRecordError("사이트가 이 연구에 속하지 않습니다.")
    _require_site_member(session, site_id, actor_user_id)


def _ensure_osdi(session: Session, study_id: str, actor_user_id: str) -> str:
    definition = session.scalar(
        select(QuestionnaireDefinition).where(
            QuestionnaireDefinition.study_id == study_id,
            QuestionnaireDefinition.code == "OSDI",
        )
    )
    items_json = json.dumps(
        [{"code": f"OSQ{index}", "type": "integer"} for index in range(1, 13)],
        ensure_ascii=False,
    )
    if definition is None:
        definition = define_questionnaire(
            session, study_id=study_id, code="OSDI", title="OSDI", actor_user_id=actor_user_id,
        )
    version = session.scalar(
        select(QuestionnaireVersion)
        .where(QuestionnaireVersion.definition_id == definition.id)
        .order_by(QuestionnaireVersion.version_number.desc())
    )
    if version is None:
        version = publish_questionnaire_version(
            session,
            definition_id=definition.id,
            version_number=1,
            items_json=items_json,
            actor_user_id=actor_user_id,
        )
    return version.id


def _store_target(
    session: Session,
    *,
    study_id: str,
    batch_id: str,
    subject_code: str,
    visit_code: str,
    item_id: str,
    target_type: str,
    target_id: str,
    value: object,
) -> str:
    digest = _value_sha(item_id, value)
    key = f"{subject_code}|{visit_code}|{item_id}"
    link = session.scalar(
        select(ImportLink).where(ImportLink.study_id == study_id, ImportLink.natural_key == key)
    )
    if link is None:
        link = ImportLink(
            study_id=study_id,
            natural_key=key,
            value_sha256=digest,
            target_type=target_type,
            target_id=target_id,
            batch_id=batch_id,
            item_id=item_id,
        )
        session.add(link)
        session.flush()
        return "created"
    if link.value_sha256 == digest:
        return "unchanged"
    session.add(ImportDiscrepancy(
        study_id=study_id,
        link_id=link.id,
        batch_id=batch_id,
        previous_sha256=link.value_sha256,
        new_sha256=digest,
        new_value_json=json.dumps({"item_id": item_id, "value": value}, ensure_ascii=False, default=str),
        status="open",
    ))
    session.flush()
    return "discrepancy"


def _apply_row(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    batch_id: str,
    sheet: ParsedSheet,
    row: ParsedRow,
    osdi_version_id: str | None,
) -> str:
    if sheet.alignment != "confirmed" or sheet.visit_code is None:
        return "skipped_unmapped"
    if "SUBJID" not in {item.item_id for item in sheet.items}:
        return "skipped_unmapped"
    subject_code = _subject_code(row.values.get("SUBJID"))
    if subject_code is None:
        return "missing_subject"
    try:
        occurred = _parse_date(row.values.get("SVDAT"))
    except ClinicalRecordError:
        return "unparsed_visit_date"
    if occurred is None:
        return "missing_visit_date"
    subject = session.scalar(
        select(StudySubject).where(
            StudySubject.study_id == study_id,
            StudySubject.subject_code == subject_code,
        )
    )
    if subject is None:
        subject = enroll_subject(
            session,
            study_id=study_id,
            site_id=site_id,
            subject_code=subject_code,
            actor_user_id=actor_user_id,
            enrolled_on=occurred,
        )
    elif subject.site_id != site_id:
        return "cross_site_subject"
    visit = session.scalar(
        select(StudyVisit).where(
            StudyVisit.subject_id == subject.id,
            StudyVisit.visit_code == sheet.visit_code,
            StudyVisit.repeat_no == 1,
        )
    )
    if visit is None:
        visit = open_visit(
            session,
            subject_id=subject.id,
            visit_code=sheet.visit_code,
            occurred_on=occurred,
            actor_user_id=actor_user_id,
        )
    elif visit.occurred_on != occurred:
        session.add(ImportValidationFinding(
            batch_id=batch_id,
            study_id=study_id,
            subject_code=subject_code,
            visit_code=sheet.visit_code,
            item_id="SVDAT",
            classification="NEEDS_HUMAN_REVIEW",
            rule_code="visit_date_conflict",
            message_code="VISIT_DATE_DIFFERS",
        ))
    response_id = None
    items_by_id = {item.item_id: item for item in sheet.items}
    for item_id, value in row.values.items():
        if value is None or item_id in {"SUBJID", "SVDAT"}:
            continue
        item = items_by_id.get(item_id)
        if item is None:
            continue
        target = canonical_target(item)
        if target is None:
            continue
        if target["kind"] == "observation":
            number = parse_number(value)
            text = None if number is not None else str(value)
            key = f"{subject_code}|{sheet.visit_code}|{item_id}"
            existing = session.scalar(
                select(ImportLink).where(ImportLink.study_id == study_id, ImportLink.natural_key == key)
            )
            if existing is None:
                try:
                    observation = create_draft_observation(
                        session,
                        visit_id=visit.id,
                        code=target["code"],
                        recorded_by=actor_user_id,
                        actor_user_id=actor_user_id,
                        laterality=target["laterality"],
                        method=target["method"],
                        repeat_index=target["repeat"],
                        value_number=number,
                        value_text=text,
                        source="import",
                    )
                except ClinicalRecordError:
                    session.add(ImportValidationFinding(
                        batch_id=batch_id,
                        study_id=study_id,
                        subject_code=subject_code,
                        visit_code=sheet.visit_code,
                        item_id=item_id,
                        classification="NEEDS_HUMAN_REVIEW",
                        rule_code="existing_observation_not_overwritten",
                        message_code="OBSERVATION_KEPT",
                    ))
                    continue
                _store_target(
                    session,
                    study_id=study_id,
                    batch_id=batch_id,
                    subject_code=subject_code,
                    visit_code=sheet.visit_code,
                    item_id=item_id,
                    target_type="observation",
                    target_id=observation.id,
                    value=number if number is not None else text,
                )
            else:
                _store_target(
                    session,
                    study_id=study_id,
                    batch_id=batch_id,
                    subject_code=subject_code,
                    visit_code=sheet.visit_code,
                    item_id=item_id,
                    target_type="observation",
                    target_id=existing.target_id,
                    value=number if number is not None else text,
                )
        elif target["kind"] == "questionnaire" and osdi_version_id is not None:
            number = parse_number(value)
            stored = number if number is not None else str(value)
            key = f"{subject_code}|{sheet.visit_code}|{item_id}"
            existing = session.scalar(
                select(ImportLink).where(ImportLink.study_id == study_id, ImportLink.natural_key == key)
            )
            if existing is None:
                if response_id is None:
                    response = start_response(
                        session,
                        version_id=osdi_version_id,
                        visit_id=visit.id,
                        recorded_by=actor_user_id,
                        actor_user_id=actor_user_id,
                    )
                    response_id = response.id
                outcome = _store_target(
                    session,
                    study_id=study_id,
                    batch_id=batch_id,
                    subject_code=subject_code,
                    visit_code=sheet.visit_code,
                    item_id=item_id,
                    target_type="questionnaire_item",
                    target_id=response_id,
                    value=stored,
                )
                if outcome == "created":
                    save_response_item(
                        session,
                        response_id,
                        actor_user_id=actor_user_id,
                        item_code=item_id,
                        value_json=json.dumps(stored, ensure_ascii=False),
                    )
            else:
                _store_target(
                    session,
                    study_id=study_id,
                    batch_id=batch_id,
                    subject_code=subject_code,
                    visit_code=sheet.visit_code,
                    item_id=item_id,
                    target_type="questionnaire_item",
                    target_id=existing.target_id,
                    value=stored,
                )
    for finding in evaluate_row(row.values):
        session.add(ImportValidationFinding(
            batch_id=batch_id,
            study_id=study_id,
            subject_code=subject_code,
            visit_code=sheet.visit_code,
            item_id=finding["item_id"],
            classification=finding["classification"],
            rule_code=finding["rule_code"],
            message_code=finding["message_code"],
        ))
    return "staged"


def confirm_import(
    session: Session,
    *,
    study_id: str,
    site_id: str,
    actor_user_id: str,
    filename: str,
    content: bytes,
    source_system: str = "external-edc",
) -> dict:
    _require_import_scope(session, study_id, site_id, actor_user_id)
    parsed = parse_workbook(content)
    existing = session.scalar(
        select(ImportSource).where(
            ImportSource.study_id == study_id,
            ImportSource.content_sha256 == parsed.content_sha256,
        )
    )
    if existing is not None:
        batch = session.scalar(
            select(ImportBatch)
            .where(ImportBatch.source_id == existing.id, ImportBatch.status == "confirmed")
            .order_by(ImportBatch.created_at.desc())
        )
        if batch is not None:
            summary = json.loads(batch.summary_json)
            summary["idempotent_replay"] = True
            summary["batch_id"] = batch.id
            return summary
    needs_osdi = any(
        item.item_id.startswith("OSQ")
        for sheet in parsed.sheets
        for item in sheet.items
    )
    with session.begin_nested():
        source = existing or ImportSource(
            study_id=study_id,
            source_system=source_system[:64],
            original_filename=_basename(filename),
            content_sha256=parsed.content_sha256,
            byte_size=parsed.byte_size,
            actor_user_id=actor_user_id,
        )
        if existing is None:
            session.add(source)
            session.flush()
        batch = ImportBatch(
            source_id=source.id,
            study_id=study_id,
            site_id=site_id,
            mapping_version=MAPPING_VERSION,
            adapter=ADAPTER_NAME,
            mode="confirm",
            status="confirmed",
            actor_user_id=actor_user_id,
            summary_json="{}",
        )
        session.add(batch)
        session.flush()
        osdi_version_id = _ensure_osdi(session, study_id, actor_user_id) if needs_osdi else None
        counts: dict[str, int] = {}
        for sheet in parsed.sheets:
            for row in sheet.rows:
                try:
                    status = _apply_row(
                        session,
                        study_id=study_id,
                        site_id=site_id,
                        actor_user_id=actor_user_id,
                        batch_id=batch.id,
                        sheet=sheet,
                        row=row,
                        osdi_version_id=osdi_version_id,
                    )
                except ClinicalRecordError as exc:
                    status = "row_error"
                    session.add(ImportStagingRow(
                        batch_id=batch.id,
                        sheet_name=row.sheet_name,
                        sheet_index=row.sheet_index,
                        source_row=row.source_row,
                        subject_code=None,
                        visit_code=row.visit_code,
                        status=status,
                        payload_json=json.dumps({"error": str(exc)}, ensure_ascii=False),
                        sensitive_hashes_json=json.dumps(row.sensitive_hashes, sort_keys=True),
                        error_code="ROW_ERROR",
                    ))
                    counts[status] = counts.get(status, 0) + 1
                    continue
                session.add(ImportStagingRow(
                    batch_id=batch.id,
                    sheet_name=row.sheet_name,
                    sheet_index=row.sheet_index,
                    source_row=row.source_row,
                    subject_code=row.values.get("SUBJID") if isinstance(row.values.get("SUBJID"), str) else None,
                    visit_code=row.visit_code,
                    status=status,
                    payload_json=json.dumps(
                        {key: value for key, value in row.values.items() if key != "SUBJID"},
                        ensure_ascii=False,
                        default=str,
                    ),
                    sensitive_hashes_json=json.dumps(row.sensitive_hashes, sort_keys=True),
                    error_code=None if status == "staged" else status.upper(),
                ))
                counts[status] = counts.get(status, 0) + 1
            if sheet.alignment != "confirmed":
                counts["unresolved_sheets"] = counts.get("unresolved_sheets", 0) + 1
        summary = _summary_from_workbook(parsed)
        summary.update({
            "persisted": True,
            "idempotent_replay": False,
            "batch_id": batch.id,
            "source_id": source.id,
            "row_status_counts": counts,
            "finding_count": session.scalar(
                select(func.count()).select_from(ImportValidationFinding).where(
                    ImportValidationFinding.batch_id == batch.id,
                )
            ) or 0,
            "discrepancy_count": session.scalar(
                select(func.count()).select_from(ImportDiscrepancy).where(ImportDiscrepancy.batch_id == batch.id)
            ) or 0,
            "automatic_finalize": False,
            "automatic_lock": False,
            "automatic_correction": False,
            "blinded_values_stored": False,
        })
        batch.summary_json = json.dumps(summary, ensure_ascii=False)
        _audit(
            session,
            study_id=study_id,
            site_id=site_id,
            actor_user_id=actor_user_id,
            action="import_confirm",
            target_type="import_batch",
            target_id=batch.id,
            payload={"content_sha256": parsed.content_sha256, "mapping_version": MAPPING_VERSION},
        )
        session.flush()
    return summary


def aggregate_workbook(content: bytes) -> dict:
    """행 값을 반환하지 않는 구조 집계. 사례 보고에 이 숫자만 쓴다."""
    parsed = parse_workbook(content)
    distinct_subjects: set[str] = set()
    subject_codes: set[str] = set()
    missing_subject = 0
    missing_date = 0
    unparsed_date = 0
    visit_rows: dict[str, int] = {}
    finding_counts: dict[str, int] = {}
    blinded = 0
    for sheet in parsed.sheets:
        if sheet.visit_code:
            visit_rows[sheet.visit_code] = visit_rows.get(sheet.visit_code, 0) + len(sheet.rows)
        for row in sheet.rows:
            blinded += len(row.blinded_item_ids)
            code = _subject_code(row.values.get("SUBJID"))
            if code is None and sheet.visit_code and any(item.item_id == "SUBJID" for item in sheet.items):
                missing_subject += 1
            elif code is not None:
                subject_codes.add(code)
                distinct_subjects.add(f"{sheet.visit_code}:{code}")
            if "SVDAT" in {item.item_id for item in sheet.items}:
                try:
                    parsed_date = _parse_date(row.values.get("SVDAT"))
                except ClinicalRecordError:
                    unparsed_date += 1
                    parsed_date = None
                if parsed_date is None and "UNPARSED" not in str(row.values.get("SVDAT")):
                    if row.values.get("SVDAT") in (None, ""):
                        missing_date += 1
            for finding in evaluate_row(row.values):
                finding_counts[finding["classification"]] = finding_counts.get(finding["classification"], 0) + 1
    summary = _summary_from_workbook(parsed)
    summary.update({
        "distinct_subject_visit_pairs": len(distinct_subjects),
        "unique_subject_count": len(subject_codes),
        "missing_subject_rows": missing_subject,
        "missing_visit_date_rows": missing_date,
        "unparsed_visit_date_rows": unparsed_date,
        "visit_row_counts": visit_rows,
        "finding_class_counts": finding_counts,
        "blinded_cell_count": blinded,
        "study_code_present_in_file": False,
        "site_code_present_in_file": False,
    })
    summary.pop("mapped_item_ids", None)
    return summary


def case_study_counts(summary: dict) -> dict:
    """집계만 반환한다. 행 값과 식별자는 포함하지 않는다."""
    return {
        "sheet_count": summary.get("sheet_count"),
        "confirmed_sheet_count": summary.get("confirmed_sheet_count"),
        "unresolved_sheet_count": summary.get("unresolved_sheet_count"),
        "data_row_count": summary.get("data_row_count"),
        "mapped_item_count": len(summary.get("mapped_item_ids") or []),
        "row_status_counts": summary.get("row_status_counts"),
        "finding_count": summary.get("finding_count"),
        "discrepancy_count": summary.get("discrepancy_count"),
        "content_sha256": summary.get("content_sha256"),
    }
