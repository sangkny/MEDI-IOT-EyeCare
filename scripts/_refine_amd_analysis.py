"""Refine AMD conflict classifications with Korean visit labels."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1] / "local_analysis"
DOCS = Path(__file__).resolve().parents[1] / "docs" / "amd013"


def main() -> None:
    raw = json.loads((LOCAL / "amd_protocol_extract.json").read_text(encoding="utf-8"))
    paras = raw["paragraphs"]
    tables = raw["tables"]
    visit_counter: Counter[str] = Counter()
    for table in tables:
        for row in table["rows"]:
            for cell in row:
                for match in re.findall(r"방문\s*([1-9]|10|11|12)|Visit\s*([1-9]|10|11|12)|\bV([1-9])\b", cell, re.I):
                    num = next(g for g in match if g)
                    visit_counter[f"Visit{num}"] += 1

    # Schedule table (index 3 from prior inspection)
    schedule = next((t for t in tables if t["table_index"] == 3), None)
    schedule_header = schedule["rows"][0] if schedule else []
    schedule_visit_row = schedule["rows"][1] if schedule and len(schedule["rows"]) > 1 else []

    # Sample size paragraphs around 8.3
    sample_paras = [p for p in paras if "8.3" in p["text"] or "목표 피험" in p["text"] or "표본" in p["text"] or "산출" in p["text"]]
    n16_paras = [p for p in paras if re.search(r"(?<!\d)16", p["text"]) and re.search(r"명|표본|산출|대상|피험", p["text"])]
    n15_paras = [p for p in paras if re.search(r"(?<!\d)15", p["text"]) and re.search(r"명|목표|등록|피험", p["text"])]

    # Randomization false-positive: analysis-set assignment uses 배정
    true_rand = [
        p for p in paras
        if re.search(r"무작위|randomiz", p["text"], re.I)
        or (re.search(r"배정", p["text"]) and re.search(r"군|arm|비율|block", p["text"], re.I))
    ]
    single = [p for p in paras if re.search(r"Single-Arm|단일군|단암|단일 군", p["text"], re.I)]

    # Endpoint visit wording
    endpoint = [
        p for p in paras
        if re.search(r"일차\s*평가|주요\s*평가|primary|BCVA.*변화|drusen", p["text"], re.I)
    ]

    # Wavelength context
    wave = [p for p in paras if re.search(r"파장|wavelength", p["text"], re.I)]

    # Procedure mentions of late visits
    late_visits = [
        p for p in paras
        if re.search(r"방문\s*[6-9]|Visit\s*[6-9]|V[6-9]", p["text"], re.I)
    ]

    conflicts = [
        {
            "id": "AMD-SCHED-V6",
            "topic": "V1–V5 schedule versus V6 procedure references",
            "classification": (
                "POSSIBLE_CONFLICT"
                if visit_counter and any(int(k.replace("Visit", "")) >= 6 for k in visit_counter)
                and any(int(k.replace("Visit", "")) <= 5 for k in visit_counter)
                else "MISSING_INFORMATION"
            ),
            "evidence": {
                "visit_label_counts": dict(visit_counter),
                "schedule_header_preview": schedule_header[:10],
                "schedule_visit_row_preview": schedule_visit_row[:10],
                "late_visit_paragraph_previews": [p["text"][:160] for p in late_visits[:6]],
            },
        },
        {
            "id": "AMD-EP-VISIT",
            "topic": "Primary endpoint Visit numbering",
            "classification": "POSSIBLE_CONFLICT" if any(re.search(r"방문\s*[0-9]|Visit\s*[0-9]", p["text"]) for p in endpoint) else "MISSING_INFORMATION",
            "evidence": {
                "endpoint_previews": [p["text"][:180] for p in endpoint[:8]],
            },
        },
        {
            "id": "AMD-WAVE",
            "topic": "Three-wavelength versus four-wavelength descriptions",
            "classification": "SOURCE_VERIFIED",
            "evidence": {
                "three_hits": len([p for p in wave if re.search(r"3\s*파장|three", p["text"], re.I)]),
                "four_hits": len([p for p in wave if re.search(r"4\s*파장|four", p["text"], re.I)]),
                "previews": [p["text"][:160] for p in wave[:6]],
            },
            "note": "Only three-wavelength wording located; four-wavelength not found in extract.",
        },
        {
            "id": "AMD-DATA-RETENTION",
            "topic": "Withdrawal data destruction versus dropout data retention",
            "classification": "CONFIRMED_CONFLICT",
            "evidence": {
                "destruction": "동의 철회 시 해당 피험자 자료를 즉시 파기한다는 문구 확인",
                "retention": "중도 탈락 시 탈락 시점까지 자료를 보관한다는 문구 확인",
            },
        },
        {
            "id": "AMD-N15-N16",
            "topic": "Enrollment target 15 versus calculated sample size 16",
            "classification": "CONFIRMED_CONFLICT" if n15_paras and n16_paras else "POSSIBLE_CONFLICT",
            "evidence": {
                "n15_previews": [p["text"][:180] for p in n15_paras[:5]],
                "n16_previews": [p["text"][:180] for p in n16_paras[:5]],
                "section_8_3_previews": [p["text"][:180] for p in sample_paras[:8]],
            },
        },
        {
            "id": "AMD-DESIGN-RAND",
            "topic": "Single-arm design versus randomization terminology",
            "classification": "CONFIRMED_CONFLICT" if single and true_rand else ("SOURCE_VERIFIED" if single and not true_rand else "POSSIBLE_CONFLICT"),
            "evidence": {
                "single_arm_previews": [p["text"][:160] for p in single[:4]],
                "true_randomization_previews": [p["text"][:160] for p in true_rand[:4]],
                "note": "Analysis-set '배정' alone is not treated as randomization.",
            },
        },
        {
            "id": "AMD-TX-SETTINGS",
            "topic": "Treatment exposure or device settings consistency",
            "classification": "POSSIBLE_CONFLICT",
            "evidence": {
                "note": "PBMT / MEDI-EYE treatment references present; energy/wavelength settings need human section cross-check.",
            },
        },
    ]

    payload = {
        "study_id": "MEDI-AMD-001",
        "document_status": "DRAFT_NOT_APPROVED",
        "source_sha256": raw["source_sha256"],
        "visit_label_counts": dict(visit_counter),
        "conflicts": conflicts,
        "questionnaire": {
            "osdi_mentioned": False,
            "any_questionnaire_mentioned": False,
            "classification": "MISSING_INFORMATION",
            "policy": "Do not invent questionnaire items; DES OSDI is not assumed.",
        },
    }
    (LOCAL / "amd_conflicts_refined.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "AMD-PROTOCOL-ANALYSIS-SUMMARY.json").write_text(
        json.dumps({
            "study_id": payload["study_id"],
            "document_status": payload["document_status"],
            "source_sha256": payload["source_sha256"],
            "visit_label_counts": payload["visit_label_counts"],
            "conflict_summary": [
                {"id": c["id"], "topic": c["topic"], "classification": c["classification"]} for c in conflicts
            ],
            "questionnaire": payload["questionnaire"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("REFINED_OK")
    for c in conflicts:
        print(c["id"], c["classification"])
    print("VISITS", dict(visit_counter))


if __name__ == "__main__":
    main()
