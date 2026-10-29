"""Classify MEDI-AMD-001 extraction and conflicts. Sanitized outputs only."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "local_analysis"
DOCS = ROOT / "docs" / "amd013"


def _has(text: str, *parts: str) -> bool:
    return all(part.lower() in text.lower() for part in parts)


def _any(text: str, *parts: str) -> bool:
    return any(part.lower() in text.lower() for part in parts)


def main() -> None:
    raw = json.loads((LOCAL / "amd_protocol_extract.json").read_text(encoding="utf-8"))
    paras = raw["paragraphs"]
    tables = raw["tables"]
    joined = "\n".join(p["text"] for p in paras)

    def find_refs(*needles: str, limit: int = 8) -> list[dict]:
        out = []
        for paragraph in paras:
            if any(needle in paragraph["text"] for needle in needles):
                out.append({
                    "paragraph_index": paragraph["i"],
                    "style": paragraph["style"],
                    "preview": paragraph["text"][:140],
                })
                if len(out) >= limit:
                    break
        return out

    def table_hits(*needles: str, limit: int = 6) -> list[dict]:
        out = []
        for table in tables:
            blob = " | ".join(" / ".join(row) for row in table["rows"][:12])
            if any(needle in blob for needle in needles):
                out.append({
                    "table_index": table["table_index"],
                    "row_count": len(table["rows"]),
                    "preview_rows": table["rows"][:4],
                })
                if len(out) >= limit:
                    break
        return out

    extraction = {
        "study_id": "MEDI-AMD-001",
        "document_status": "DRAFT",
        "source_filename": raw["source_filename"],
        "source_sha256": raw["source_sha256"],
        "design": {
            "refs": find_refs("단일군", "단암", "single-arm", "단일 군", "전향", "탐색", "pilot", "무작위"),
            "notes": "Design and randomization wording collected for conflict check.",
        },
        "enrollment_target": {
            "refs": find_refs("15명", "15 명", "대상자 수", "등록", "피험자", "sample size", "표본", "16명", "16 명"),
        },
        "visit_schedule": {
            "paragraph_refs": find_refs("V1", "V2", "V3", "V4", "V5", "V6", "방문 일정", "Visit"),
            "table_refs": table_hits("V1", "V2", "V3", "V4", "V5", "V6", "방문"),
        },
        "visit_windows": {
            "refs": find_refs("±", "윈도우", "window", "방문창", "허용"),
        },
        "inclusion_exclusion": {
            "refs": find_refs("선정기준", "제외기준", "Inclusion", "Exclusion", "선정 기준", "제외 기준"),
            "table_refs": table_hits("선정", "제외", "Inclusion", "Exclusion"),
        },
        "study_eye": {
            "refs": find_refs("연구안", "Study Eye", "연구 안", "대상안", "우안", "좌안"),
        },
        "endpoints": {
            "refs": find_refs("일차 평가변수", "주요 평가변수", "secondary", "이차", "endpoint", "평가변수", "BCVA", "drusen"),
        },
        "assessments": {
            "refs": find_refs("BCVA", "OCT", "FAF", "세극등", "시야", "IOP", "안압", "안저", "파장"),
            "table_refs": table_hits("BCVA", "OCT", "IOP", "FAF", "VF"),
        },
        "treatment_exposure": {
            "refs": find_refs("치료", "조사", "노광", "exposure", "파장", "device", "장비", "에너지"),
        },
        "ae_safety": {
            "refs": find_refs("이상반응", "Adverse", "AE", "안전성", "추적"),
        },
        "analysis_populations": {
            "refs": find_refs("FAS", "SS", "PPS", "안전성 분석", "전체 분석", "분석 집단"),
        },
        "statistics": {
            "refs": find_refs("통계", "통계분석", "기술통계", "유의", "검정", "결측"),
        },
        "questionnaire": {
            "refs": find_refs("설문", "OSDI", "questionnaire", "QOL", "NEI VFQ"),
            "note": "Do not assume OSDI from MEDI-DES-001.",
        },
        "withdrawal_retention": {
            "refs": find_refs("철회", "중도탈락", "탈락", "폐기", "파기", "보관", "삭제", "동의 철회"),
        },
    }

    # Keyword frequency for wavelength / sample / randomization
    wavelength3 = len(re.findall(r"3\s*파장|세\s*파장|three[-\s]?wavelength|3[-\s]?wavelength", joined, re.I))
    wavelength4 = len(re.findall(r"4\s*파장|네\s*파장|four[-\s]?wavelength|4[-\s]?wavelength", joined, re.I))
    n15 = len(re.findall(r"(?<!\d)15\s*명|(?<!\d)N\s*=\s*15|(?<!\d)n\s*=\s*15", joined))
    n16 = len(re.findall(r"(?<!\d)16\s*명|(?<!\d)N\s*=\s*16|(?<!\d)n\s*=\s*16|표본\s*수[^\n]{0,40}16", joined))
    random_hits = [p for p in paras if _any(p["text"], "무작위", "randomiz", "배정")]
    single_arm = [p for p in paras if _any(p["text"], "단일군", "단암", "single-arm", "단일 군", "단일군 설계")]
    destroy = [p for p in paras if _any(p["text"], "폐기", "파기", "삭제") and _any(p["text"], "철회", "동의", "자료", "데이터")]
    retain = [p for p in paras if _any(p["text"], "보관", "유지", "보존") and _any(p["text"], "탈락", "중도", "자료", "데이터")]

    # V1-V6 mentions in tables
    visit_counter = Counter()
    for table in tables:
        for row in table["rows"]:
            for cell in row:
                for visit in ("V1", "V2", "V3", "V4", "V5", "V6"):
                    if re.search(rf"\b{visit}\b", cell):
                        visit_counter[visit] += 1

    conflicts = []

    # 1. V1-V5 vs V6
    conflicts.append({
        "id": "AMD-SCHED-V6",
        "topic": "V1–V5 schedule versus V6 procedure references",
        "classification": "POSSIBLE_CONFLICT" if visit_counter.get("V6") and visit_counter.get("V5") else "MISSING_INFORMATION",
        "evidence": {
            "visit_cell_mentions": dict(visit_counter),
            "sample_refs": extraction["visit_schedule"]["table_refs"][:2],
        },
        "note": "Manual review required for whether V6 appears only as procedure footnote while schedule stops at V5.",
    })

    # 2. Primary endpoint visit numbering
    endpoint_preview = [r["preview"] for r in extraction["endpoints"]["refs"][:10]]
    conflicts.append({
        "id": "AMD-EP-VISIT",
        "topic": "Primary endpoint Visit numbering",
        "classification": "POSSIBLE_CONFLICT" if any("V6" in t or "V5" in t for t in endpoint_preview) else "MISSING_INFORMATION",
        "evidence": {"endpoint_previews": endpoint_preview[:6]},
        "note": "Confirm which visit is named for primary endpoint evaluation.",
    })

    # 3. wavelength
    if wavelength3 and wavelength4:
        wclass = "CONFIRMED_CONFLICT"
    elif wavelength3 or wavelength4:
        wclass = "SOURCE_VERIFIED"
    else:
        wclass = "MISSING_INFORMATION"
    conflicts.append({
        "id": "AMD-WAVE",
        "topic": "Three-wavelength versus four-wavelength descriptions",
        "classification": wclass,
        "evidence": {"three_wavelength_hits": wavelength3, "four_wavelength_hits": wavelength4},
    })

    # 4. withdrawal destruction vs dropout retention
    if destroy and retain:
        wret = "CONFIRMED_CONFLICT"
    elif destroy or retain:
        wret = "POSSIBLE_CONFLICT"
    else:
        wret = "MISSING_INFORMATION"
    conflicts.append({
        "id": "AMD-DATA-RETENTION",
        "topic": "Withdrawal data destruction versus dropout data retention",
        "classification": wret,
        "evidence": {
            "destruction_previews": [p["text"][:140] for p in destroy[:4]],
            "retention_previews": [p["text"][:140] for p in retain[:4]],
        },
    })

    # 5. 15 vs 16
    if n15 and n16:
        sample_class = "CONFIRMED_CONFLICT"
    elif n15 or n16:
        sample_class = "POSSIBLE_CONFLICT"
    else:
        sample_class = "MISSING_INFORMATION"
    conflicts.append({
        "id": "AMD-N15-N16",
        "topic": "Enrollment target 15 versus calculated sample size 16",
        "classification": sample_class,
        "evidence": {
            "n15_pattern_hits": n15,
            "n16_pattern_hits": n16,
            "enrollment_previews": [r["preview"] for r in extraction["enrollment_target"]["refs"][:8]],
        },
    })

    # 6. single-arm vs randomization
    if single_arm and random_hits:
        design_class = "CONFIRMED_CONFLICT"
    elif single_arm or random_hits:
        design_class = "POSSIBLE_CONFLICT"
    else:
        design_class = "MISSING_INFORMATION"
    conflicts.append({
        "id": "AMD-DESIGN-RAND",
        "topic": "Single-arm design versus randomization terminology",
        "classification": design_class,
        "evidence": {
            "single_arm_previews": [p["text"][:140] for p in single_arm[:4]],
            "randomization_previews": [p["text"][:140] for p in random_hits[:4]],
        },
    })

    # 7. treatment/device settings inconsistency
    treat_refs = extraction["treatment_exposure"]["refs"]
    conflicts.append({
        "id": "AMD-TX-SETTINGS",
        "topic": "Treatment exposure or device settings consistency",
        "classification": "POSSIBLE_CONFLICT" if len(treat_refs) >= 2 else "MISSING_INFORMATION",
        "evidence": {"treatment_previews": [r["preview"] for r in treat_refs[:6]]},
        "note": "Device energy/wavelength settings need human cross-check across sections.",
    })

    # Questionnaire presence
    q_refs = extraction["questionnaire"]["refs"]
    questionnaire_status = {
        "osdi_mentioned": any("OSDI" in r["preview"] for r in q_refs),
        "any_questionnaire_mentioned": bool(q_refs),
        "classification": "SOURCE_VERIFIED" if q_refs else "MISSING_INFORMATION",
        "policy": "Do not invent questionnaire items; do not import DES OSDI by default.",
        "previews": [r["preview"] for r in q_refs[:5]],
    }

    DOCS.mkdir(parents=True, exist_ok=True)
    (LOCAL / "amd_extraction_matrix.json").write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (LOCAL / "amd_conflicts.json").write_text(
        json.dumps({"conflicts": conflicts, "questionnaire": questionnaire_status}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Sanitized public report fragment (previews only, no full protocol)
    summary = {
        "study_id": "MEDI-AMD-001",
        "document_status": "DRAFT_NOT_APPROVED",
        "source_sha256": raw["source_sha256"],
        "paragraph_count": raw["paragraph_count"],
        "table_count": raw["table_count"],
        "visit_cell_mentions": dict(visit_counter),
        "conflict_summary": [
            {"id": c["id"], "topic": c["topic"], "classification": c["classification"]} for c in conflicts
        ],
        "questionnaire": questionnaire_status,
        "counts": {
            "wavelength3": wavelength3,
            "wavelength4": wavelength4,
            "n15": n15,
            "n16": n16,
            "single_arm_paras": len(single_arm),
            "randomization_paras": len(random_hits),
        },
    }
    (DOCS / "AMD-PROTOCOL-ANALYSIS-SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("ANALYSIS_OK")
    for item in summary["conflict_summary"]:
        print(item["id"], item["classification"])
    print("Q", questionnaire_status["classification"], "OSDI", questionnaire_status["osdi_mentioned"])


if __name__ == "__main__":
    main()
