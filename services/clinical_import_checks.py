"""가져온 값의 결정적 점검. 원본을 고치지 않고 분류만 반환한다."""
from __future__ import annotations

import re

FINDING_INVALID = "INVALID_BY_RULE"
FINDING_SUSPECTED = "SUSPECTED_ENTRY_ERROR"
FINDING_OUTLIER = "STATISTICAL_OUTLIER"
FINDING_REVIEW = "NEEDS_HUMAN_REVIEW"
OSDI_FORMULA_NOTE = "ASSUMPTION_NOT_PROTOCOL_THRESHOLD"


def parse_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    if "," in text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _repeat_groups(values: dict[str, object]) -> dict[str, list[tuple[str, float]]]:
    groups: dict[str, list[tuple[str, float]]] = {}
    for item_id, raw in values.items():
        match = re.fullmatch(r"TB(OD|OS)ORS([123])", item_id)
        if match is None:
            continue
        number = parse_number(raw)
        if number is None:
            continue
        groups.setdefault(match.group(1), []).append((item_id, number))
    return groups


def evaluate_row(values: dict[str, object]) -> list[dict]:
    findings: list[dict] = []
    for item_id, raw in values.items():
        if raw is None or str(raw).strip() == "":
            continue
        if parse_number(raw) is None and not isinstance(raw, (int, float)):
            if re.fullmatch(r"ST(OD|OS)ORS|OSSCORE", item_id):
                findings.append({
                    "classification": FINDING_REVIEW,
                    "rule_code": "numeric_text_unresolved",
                    "message_code": "CODE_OR_TOKEN_UNRESOLVED",
                    "item_id": item_id,
                })
            elif re.fullmatch(r"OSQ\d+|OSSUM|OSNUM", item_id):
                findings.append({
                    "classification": FINDING_REVIEW,
                    "rule_code": "osdi_code_list_unresolved",
                    "message_code": "CODE_LIST_UNRESOLVED",
                    "item_id": item_id,
                })
            if re.fullmatch(r"ST(OD|OS)ORS|OSQ\d+|OSSCORE|OSSUM|OSNUM", item_id):
                continue
        number = parse_number(raw)
        if number is not None and number < 0 and re.fullmatch(
            r"TB(OD|OS)ORS[123]|TB(OD|OS)ORSAV|ST(OD|OS)ORS|ST(OD|OS)NORS|OSSCORE",
            item_id,
        ):
            findings.append({
                "classification": FINDING_INVALID,
                "rule_code": "negative_measurement",
                "message_code": "NEGATIVE_NOT_ALLOWED",
                "item_id": item_id,
            })
    for eye, repeats in _repeat_groups(values).items():
        numbers = [number for _item, number in repeats]
        if len(numbers) >= 2:
            high = max(numbers)
            low = min(number for number in numbers if number > 0) if any(number > 0 for number in numbers) else None
            if low not in (None, 0) and 8 <= (high / low) <= 12:
                findings.append({
                    "classification": FINDING_SUSPECTED,
                    "rule_code": "decimal_shift_among_repeats",
                    "message_code": "REPEAT_SCALE_GAP",
                    "item_id": f"TB{eye}ORS",
                })
        average_id = f"TB{eye}ORSAV"
        average = parse_number(values.get(average_id))
        if average is not None and numbers:
            mean = sum(numbers) / len(numbers)
            if abs(average - mean) > 0.05:
                findings.append({
                    "classification": FINDING_SUSPECTED,
                    "rule_code": "reported_average_mismatch",
                    "message_code": "AVERAGE_DIFFERS",
                    "item_id": average_id,
                })
    answered = []
    for index in range(1, 13):
        number = parse_number(values.get(f"OSQ{index}"))
        if number is not None:
            answered.append(number)
    score = parse_number(values.get("OSSCORE"))
    count = parse_number(values.get("OSNUM"))
    if count is not None and answered and int(count) != len(answered):
        findings.append({
            "classification": FINDING_REVIEW,
            "rule_code": "osdi_count_mismatch",
            "message_code": OSDI_FORMULA_NOTE,
            "item_id": "OSNUM",
        })
    if score is not None and answered:
        expected = sum(answered) * 25 / len(answered)
        if abs(score - expected) > 0.5:
            findings.append({
                "classification": FINDING_REVIEW,
                "rule_code": "osdi_score_formula_mismatch",
                "message_code": OSDI_FORMULA_NOTE,
                "item_id": "OSSCORE",
            })
    return findings
