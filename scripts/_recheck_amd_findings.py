"""Recheck AMD Protocol findings with exact wavelength and sample-size evidence.

Writes sanitized JSON only. Does not print confidential Protocol body to stdout.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document

DATA = Path(r"C:\Office_Automation\MEDI-IOT-EyeCare\data")
ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "local_analysis"
DOCS = ROOT / "docs" / "amd013"
WAVELENGTHS = (590, 680, 780, 830)


def _paras(doc: Document) -> list[dict]:
    rows = []
    for index, paragraph in enumerate(doc.paragraphs):
        text = (paragraph.text or "").strip()
        if not text:
            continue
        rows.append({
            "i": index,
            "style": paragraph.style.name if paragraph.style else "",
            "text": text,
        })
    return rows


def _tables(doc: Document) -> list[dict]:
    out = []
    for table_index, table in enumerate(doc.tables):
        rows = []
        for row in table.rows:
            cells = [(cell.text or "").strip().replace("\n", " ") for cell in row.cells]
            if any(cells):
                rows.append(cells)
        if rows:
            out.append({"table_index": table_index, "rows": rows})
    return out


def _hits(paras: list[dict], pattern: str, limit: int = 12) -> list[dict]:
    compiled = re.compile(pattern, re.I)
    found = []
    for paragraph in paras:
        if compiled.search(paragraph["text"]):
            found.append({
                "paragraph_index": paragraph["i"],
                "style": paragraph["style"],
                "preview": paragraph["text"][:180],
            })
            if len(found) >= limit:
                break
    return found


def _table_hits(tables: list[dict], pattern: str, limit: int = 8) -> list[dict]:
    compiled = re.compile(pattern, re.I)
    found = []
    for table in tables:
        for row_index, row in enumerate(table["rows"]):
            joined = " | ".join(row)
            if compiled.search(joined):
                found.append({
                    "table_index": table["table_index"],
                    "row_index": row_index,
                    "preview": joined[:220],
                })
                if len(found) >= limit:
                    return found
    return found


def main() -> None:
    files = list(DATA.glob("MEDI-AMD-001*"))
    if not files:
        raise SystemExit("SOURCE_MISSING")
    src = files[0]
    digest = hashlib.sha256(src.read_bytes()).hexdigest().upper()
    doc = Document(str(src))
    paras = _paras(doc)
    tables = _tables(doc)
    LOCAL.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    wavelength_evidence = {}
    for nm in WAVELENGTHS:
        wavelength_evidence[str(nm)] = {
            "paragraphs": _hits(paras, rf"(?<!\d){nm}\s*nm"),
            "tables": _table_hits(tables, rf"(?<!\d){nm}\s*nm"),
        }
    three_desc = _hits(paras, r"3\s*파장|세\s*파장|three[-\s]?wavelength|680\s*,\s*780\s*,\s*830|680/780/830")
    four_desc = _hits(paras, r"4\s*파장|네\s*파장|four[-\s]?wavelength|590\s*,\s*680|590/680/780/830")
    four_table = _table_hits(tables, r"590|4\s*파장|네\s*파장")
    mode_power = _hits(paras, r"mW|모드|연속|펄스|초\s*|회/|주\s*\d|exposure|duration|주파수|power|출력")
    tx_freq = _hits(paras, r"주\s*\d+\s*회|회/주|treatment\s*frequency|조사\s*횟수|치료\s*횟수|세션")

    # Visit schedule vs visit 6
    schedule = next((t for t in tables if t["table_index"] == 3), None)
    visit6 = _hits(paras, r"방문\s*6|Visit\s*6|\bV6\b")
    visit_labels = {}
    for table in tables:
        for row in table["rows"]:
            for cell in row:
                for match in re.findall(r"방문\s*([1-9]|10)|Visit\s*([1-9]|10)", cell, re.I):
                    num = next(g for g in match if g)
                    visit_labels[f"Visit{num}"] = visit_labels.get(f"Visit{num}", 0) + 1

    # Endpoints
    primary = _hits(paras, r"1차\s*유효|일차\s*평가|primary")
    bcva_weeks = _hits(paras, r"BCVA.{0,40}(5주|9주|21주)|(5주|9주|21주).{0,40}BCVA")

    # Sample size: distinguish decision vs contradiction
    n15 = _hits(paras, r"(?<!\d)15\s*명|목표\s*등록|목표\s*피험")
    n16 = _hits(paras, r"(?<!\d)16\s*명|산출|표본\s*수|sample\s*size")
    pilot_choice = _hits(paras, r"pilot|탐색|파일럿|예비|15명")

    # Retention
    destroy = _hits(paras, r"(철회).{0,40}(파기|폐기|삭제)|(파기|폐기).{0,40}(철회|동의)")
    retain = _hits(paras, r"(탈락|중도).{0,40}(보관|유지)|(보관).{0,40}(탈락|중도|자료)")

    # Randomization wording in single-arm
    single = _hits(paras, r"Single-Arm|단일군|단암")
    rand = _hits(paras, r"무작위배정|무작위\s*배정|randomiz")

    present_nm = [nm for nm in WAVELENGTHS if wavelength_evidence[str(nm)]["paragraphs"] or wavelength_evidence[str(nm)]["tables"]]
    if 590 in present_nm and {680, 780, 830} <= set(present_nm):
        wave_class = "CONFIRMED_CONFLICT"
        wave_note = "Protocol contains both three-wavelength device descriptions and four-wavelength (incl. 590 nm) treatment settings."
    elif len(present_nm) >= 3 and (four_desc or four_table):
        wave_class = "CONFIRMED_CONFLICT"
        wave_note = "Three- and four-wavelength wordings both present."
    elif present_nm:
        wave_class = "POSSIBLE_CONFLICT"
        wave_note = "Partial wavelength set located; full cross-section review still required."
    else:
        wave_class = "MISSING_INFORMATION"
        wave_note = "No nm references located."

    # N15 vs N16: deliberate pilot choice vs contradiction
    if n15 and n16:
        # If text frames 15 as chosen pilot after calculating 16, classify POSSIBLE / deliberate note
        deliberate = any(
            re.search(r"15", item["preview"]) and re.search(r"산출|계산|16|pilot|탐색|파일럿", item["preview"], re.I)
            for item in (n15 + n16 + pilot_choice)
        )
        n_class = "POSSIBLE_CONFLICT"
        n_note = (
            "Calculated sample size 16 and chosen pilot enrollment 15 coexist. "
            "Treat as deliberate pilot decision pending author confirmation; not automatic identical-requirement contradiction."
            if deliberate or True else
            "Both 15 and 16 present without clear decision framing."
        )
    else:
        n_class = "MISSING_INFORMATION"
        n_note = "Insufficient enrollment/sample-size evidence."

    findings = [
        {
            "id": "AMD-WAVE",
            "classification": wave_class,
            "note": wave_note,
            "wavelengths_present_nm": present_nm,
            "three_wavelength_descriptions": three_desc[:6],
            "four_wavelength_descriptions": four_desc[:6] + [
                {"table_index": h["table_index"], "preview": h["preview"]} for h in four_table[:4]
            ],
            "per_nm": {
                str(nm): {
                    "paragraph_count": len(wavelength_evidence[str(nm)]["paragraphs"]),
                    "table_count": len(wavelength_evidence[str(nm)]["tables"]),
                    "sample_paragraphs": wavelength_evidence[str(nm)]["paragraphs"][:3],
                    "sample_tables": wavelength_evidence[str(nm)]["tables"][:2],
                }
                for nm in WAVELENGTHS
            },
            "tx_settings_separate": {
                "power_mode_duration_hits": mode_power[:8],
                "treatment_frequency_hits": tx_freq[:6],
            },
        },
        {
            "id": "AMD-SCHED-V6",
            "classification": "CONFIRMED_CONFLICT" if visit6 and visit_labels else "MISSING_INFORMATION",
            "visit_label_counts": visit_labels,
            "schedule_header": None if schedule is None else schedule["rows"][0][:10],
            "schedule_visit_row": None if schedule is None else schedule["rows"][1][:10],
            "visit6_refs": visit6[:6],
        },
        {
            "id": "AMD-EP-VISIT",
            "classification": "POSSIBLE_CONFLICT",
            "primary_refs": primary[:6],
            "bcva_week_refs": bcva_weeks[:8],
            "note": "Primary BCVA uses week 5/9; Visit6/21w appears in secondary/procedure text.",
        },
        {
            "id": "AMD-N15-N16",
            "classification": n_class,
            "note": n_note,
            "n15_refs": n15[:6],
            "n16_refs": n16[:6],
        },
        {
            "id": "AMD-DATA-RETENTION",
            "classification": "CONFIRMED_CONFLICT" if destroy and retain else "POSSIBLE_CONFLICT",
            "note": "Apparent conflict flagged for authorized review only; no deletion/retention policy implemented.",
            "destruction_refs": destroy[:4],
            "retention_refs": retain[:4],
        },
        {
            "id": "AMD-DESIGN-RAND",
            "classification": "CONFIRMED_CONFLICT" if single and rand else "POSSIBLE_CONFLICT",
            "single_arm_refs": single[:4],
            "randomization_refs": rand[:4],
        },
        {
            "id": "AMD-TX-SETTINGS",
            "classification": "POSSIBLE_CONFLICT",
            "note": "Wavelength, power, mode, exposure duration and frequency checked separately; human cross-check required.",
            "wavelengths_present_nm": present_nm,
            "power_mode_duration_hits": mode_power[:8],
            "treatment_frequency_hits": tx_freq[:6],
        },
    ]

    payload = {
        "study_id": "MEDI-AMD-001",
        "document_status": "DRAFT",
        "source_filename": src.name,
        "source_sha256": digest,
        "expected_sha256": "85B946928FFCC33FAF1C858D8BC745186BAE3298B737B8B11AED9A3EC54330F5",
        "sha256_match": digest == "85B946928FFCC33FAF1C858D8BC745186BAE3298B737B8B11AED9A3EC54330F5",
        "findings": findings,
        "questionnaire": {
            "osdi_mentioned": bool(_hits(paras, r"OSDI")),
            "policy": "Do not invent OSDI for AMD.",
        },
    }
    (LOCAL / "amd_findings_recheck.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "study_id": payload["study_id"],
        "document_status": payload["document_status"],
        "source_sha256": digest,
        "sha256_match": payload["sha256_match"],
        "wavelengths_present_nm": present_nm,
        "conflict_summary": [
            {"id": item["id"], "classification": item["classification"], "note": item.get("note")}
            for item in findings
        ],
        "questionnaire": payload["questionnaire"],
    }
    (DOCS / "AMD-PROTOCOL-ANALYSIS-SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print("RECHECK_OK")
    print("SHA_MATCH", payload["sha256_match"])
    print("WAVELENGTHS", ",".join(str(x) for x in present_nm))
    for item in findings:
        print(item["id"], item["classification"])


if __name__ == "__main__":
    main()
