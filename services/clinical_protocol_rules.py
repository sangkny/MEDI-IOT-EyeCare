"""MEDI-DES-001 계획서 1.3에서 추출한 규칙. 기본 가져오기에는 적용하지 않는다.

상태는 EXTRACTED다. 승인 없이 ACTIVE로 바꾸지 않으며 잠금이나 확정에 쓰지 않는다.
호출자가 규칙 묶음 ID를 명시할 때만 권고 소견을 만든다. 원본 값은 바꾸지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from services.clinical_import_checks import parse_number
from services.clinical_import_parse import ResponseChoice

PACK_ID = "medi-des-001-v1.3"
PROTOCOL_VERSION = "1.3"
PROTOCOL_DATE = "2025-05-19"
PROTOCOL_STATUS = "UNRESOLVED"
FINDING_ADVISORY = "NEEDS_HUMAN_REVIEW"


@dataclass(frozen=True)
class ProtocolRule:
    rule_id: str
    study_scope: str
    protocol_version: str
    source_reference: str
    section: str
    variable: str
    unit: str | None
    source_fields: tuple[str, ...]
    logic: str
    severity: str
    effective_status: str
    approval_status: str


def rule_pack() -> tuple[ProtocolRule, ...]:
    common = {
        "study_scope": "MEDI-DES-001",
        "protocol_version": PROTOCOL_VERSION,
        "effective_status": "EXTRACTED",
        "approval_status": "AWAITING_APPROVAL",
    }
    return (
        ProtocolRule(
            rule_id="OSDI-ITEMS-001",
            source_reference="부록 1, p.91-93",
            section="11.1 주석 17, 부록 1",
            variable="OSDI",
            unit="score",
            source_fields=tuple(f"OSQ{index}" for index in range(1, 13)),
            logic="12문항. 임상 점수 0-4. 6-12번의 해당 없음은 점수에서 제외한다.",
            severity="advisory",
            **common,
        ),
        ProtocolRule(
            rule_id="OSDI-FORMULA-001",
            source_reference="부록 1, p.91",
            section="부록 1 계산식",
            variable="OSSCORE",
            unit="score",
            source_fields=("OSQ1", "OSQ12", "OSNUM", "OSSUM", "OSSCORE"),
            logic="대답한 문항 점수 합 x 25 / 대답한 문항 수. 해당 없음은 0이 아니다.",
            severity="advisory",
            **common,
        ),
        ProtocolRule(
            rule_id="TBUT-MEAN-001",
            source_reference="p.49, p.55 주석 13",
            section="10.2.4.12 (1), 11.1 주석 13",
            variable="TBUT",
            unit="s",
            source_fields=("TBODORS1", "TBODORS2", "TBODORS3", "TBODORSAV", "TBOSORS1", "TBOSORS2", "TBOSORS3", "TBOSORSAV"),
            logic="플루오레세인 눈물막 파괴시간을 세극등에서 3회 측정한 뒤 평균한다.",
            severity="advisory",
            **common,
        ),
        ProtocolRule(
            rule_id="SCHIRMER-METHOD-001",
            source_reference="p.50-51, p.55 주석 14",
            section="10.2.4.12 (2), 11.1 주석 14",
            variable="SCHIRMER",
            unit="mm/5min",
            source_fields=("STODORS", "STOSORS"),
            logic="점안 마취 없이 5분, 양안, 소수 첫째 자리. 열 이름만으로 방법을 추정하지 않는다.",
            severity="advisory",
            **common,
        ),
        ProtocolRule(
            rule_id="VISIT-WINDOW-001",
            source_reference="p.46 10.2.3과 p.53-59 11.1-11.2",
            section="10.2.3, 11.1, 11.2",
            variable="VISIT_WINDOW",
            unit=None,
            source_fields=("SVDAT",),
            logic="10.2.3은 방문 3-6을 ±3일로, 11.1과 11.2는 ±7일로 적는다. 허용 기간 판정은 하지 않는다.",
            severity="conflict",
            **common,
        ),
        ProtocolRule(
            rule_id="SCREENING-ID-001",
            source_reference="p.56-57",
            section="11.2.1",
            variable="SUBJID",
            unit=None,
            source_fields=("SUBJID",),
            logic="스크리닝 번호 예시는 SA-001이다. 기본 가져오기에서 이 형식을 강제하지 않는다.",
            severity="advisory",
            **common,
        ),
    )


def promote_rule(rule: ProtocolRule, status: str) -> ProtocolRule:
    if status == "ACTIVE" and rule.approval_status != "APPROVED":
        raise ValueError("승인 전 규칙은 ACTIVE가 될 수 없습니다.")
    return ProtocolRule(
        rule_id=rule.rule_id,
        study_scope=rule.study_scope,
        protocol_version=rule.protocol_version,
        source_reference=rule.source_reference,
        section=rule.section,
        variable=rule.variable,
        unit=rule.unit,
        source_fields=rule.source_fields,
        logic=rule.logic,
        severity=rule.severity,
        effective_status=status,
        approval_status=rule.approval_status,
    )


def visit_assessments() -> dict[str, dict[str, bool]]:
    """11.2 절차와 11.1 일정이 같이 말하는 검사만 참이다."""
    return {
        "V1": {"TBUT": True, "SCHIRMER": True, "OSDI": True, "FCSS": True, "LGCSS": False, "window_check": False},
        "V2": {"TBUT": True, "SCHIRMER": True, "OSDI": True, "FCSS": True, "LGCSS": True, "window_check": False},
        "V3": {"TBUT": True, "SCHIRMER": True, "OSDI": True, "FCSS": True, "LGCSS": True, "window_check": False},
        "V4": {"TBUT": True, "SCHIRMER": True, "OSDI": True, "FCSS": True, "LGCSS": True, "window_check": False},
        "V5": {"TBUT": False, "SCHIRMER": False, "OSDI": False, "FCSS": False, "LGCSS": False, "window_check": False},
        "V6": {"TBUT": True, "SCHIRMER": True, "OSDI": True, "FCSS": True, "LGCSS": True, "window_check": False},
    }


def window_conflict() -> dict[str, str]:
    return {
        "status": "CONFLICTING",
        "section_10_2_3": "방문 3-6 ±3일",
        "section_11": "방문 3-6 ±7일",
        "validation": "NOT_IMPLEMENTED",
    }


def _reported_number(value: object) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    direct = parse_number(value)
    if direct is not None:
        return direct
    text = re.sub(r"[가-힣\s]", "", str(value)).removesuffix("mm").strip()
    return parse_number(text)


def _choice_result(raw: object, choices: tuple[ResponseChoice, ...]) -> tuple[str, int | None]:
    if raw is None or str(raw).strip() == "":
        return "blank", None
    text = str(raw).strip()
    for choice in choices:
        if text == choice.label:
            if choice.score is None:
                return "not_applicable", None
            return "scored", choice.score
    return "unresolved", None


def advisory_findings(
    values: dict[str, object],
    choices_by_item: dict[str, tuple[ResponseChoice, ...]] | None = None,
) -> list[dict]:
    """권고 소견만 반환한다. 값을 고치거나 확정 상태로 올리지 않는다."""
    choices_by_item = choices_by_item or {}
    findings: list[dict] = []
    scored: list[int] = []
    unresolved = False
    for index in range(1, 13):
        item_id = f"OSQ{index}"
        if item_id not in values and item_id not in choices_by_item:
            continue
        kind, score = _choice_result(values.get(item_id), choices_by_item.get(item_id, ()))
        if kind == "unresolved" and values.get(item_id) not in (None, ""):
            unresolved = True
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "OSDI-ITEMS-001",
                "message_code": "RESPONSE_CODE_UNRESOLVED",
                "item_id": item_id,
            })
        elif kind == "scored" and score is not None:
            if score < 0 or score > 4:
                findings.append({
                    "classification": FINDING_ADVISORY,
                    "rule_code": "OSDI-ITEMS-001",
                    "message_code": "RESPONSE_CODE_UNRESOLVED",
                    "item_id": item_id,
                })
            else:
                scored.append(score)
    reported = _reported_number(values.get("OSSCORE"))
    if reported is not None and scored and not unresolved:
        expected = sum(scored) * 25 / len(scored)
        difference = abs(reported - expected)
        if difference > 0.5:
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "OSDI-FORMULA-001",
                "message_code": "SCORING_MISMATCH",
                "item_id": "OSSCORE",
            })
        elif difference > 0.05:
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "OSDI-FORMULA-001",
                "message_code": "ROUNDING_DIFFERENCE",
                "item_id": "OSSCORE",
            })
    for eye in ("OD", "OS"):
        repeats = []
        raw_present = False
        non_numeric = False
        for index in range(1, 4):
            item_id = f"TB{eye}ORS{index}"
            if values.get(item_id) in (None, ""):
                continue
            raw_present = True
            number = parse_number(values.get(item_id))
            if number is None:
                non_numeric = True
            else:
                repeats.append(number)
        if not raw_present:
            continue
        if non_numeric:
            continue
        if len(repeats) < 3:
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "TBUT-MEAN-001",
                "message_code": "MISSING_ITEM",
                "item_id": f"TB{eye}ORS",
            })
            continue
        average = parse_number(values.get(f"TB{eye}ORSAV"))
        if average is None:
            continue
        if abs(average - (sum(repeats) / 3)) > 0.05:
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "TBUT-MEAN-001",
                "message_code": "SCORING_MISMATCH",
                "item_id": f"TB{eye}ORSAV",
            })
    for item_id in ("STODORS", "STOSORS"):
        number = _reported_number(values.get(item_id))
        if number is None:
            continue
        text = f"{number:.6f}".rstrip("0")
        fraction = text.split(".")[1] if "." in text else ""
        if len(fraction) > 1:
            findings.append({
                "classification": FINDING_ADVISORY,
                "rule_code": "SCHIRMER-METHOD-001",
                "message_code": "ROUNDING_DIFFERENCE",
                "item_id": item_id,
            })
    return findings
