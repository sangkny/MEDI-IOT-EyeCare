#!/usr/bin/env python3
"""
파일명: add_test_history.py
목적: tests/scripts 파일 히스토리 docstring 자동 추가
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

파일 상단 docstring/주석 히스토리 블록 자동 추가.

사용:
  PYTHONPATH=. python3 scripts/add_test_history.py tests/
  PYTHONPATH=. python3 scripts/add_test_history.py scripts/
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

TODAY = "2026-06-11"

PURPOSES: dict[str, str] = {
    "test_comprehensive_fundus.py": "5질환 동시 진단 comprehensive API — fast/precise, v10c ONNX, 응답 구조",
    "test_diagnosis_pipeline_four_agent.py": "4-에이전트 진단 파이프라인 APPROVE/REVISE/REJECT — mock unit + slow LLM",
    "test_diagnosis_pipeline.py": "DR DecisionGate — REVISE/REJECT/APPROVE 분기 (confidence threshold)",
    "test_fhir_export.py": "FHIR R4 Bundle 생성·내보내기 — Observation + DiagnosticReport",
    "test_glaucoma_cnn.py": "Glaucoma CNN (glaucoma_v2 ONNX) 추론 검증",
    "test_glaucoma_gradcam.py": "GradCAM++ 히트맵 — optic_disc, cup_disc_asymmetry 등 레이블",
    "test_cdr_estimator.py": "CDR (Cup-to-Disc Ratio) 추정 검증",
    "test_images.py": "이미지 전처리 — CLAHE, resize, preprocess_fundus_array",
    "test_retinal_cnn.py": "DR retinal_v4 ONNX 추론 — QWK 기준",
    "test_multitask_model.py": "v10c 5-head MultiTaskV10Model — V10BatchLabels, collate, eval",
    "test_v10_export.py": "export_v10.py 5-head ONNX export — 출력 shape 검증",
    "test_comprehensive_modes.py": "fast/precise 모드 분기 — inference_mode, inference_time_ms",
    "medi-regression.sh": "MEDI-IOT 회귀 — unit/smoke/e2e/full 모드",
    "git_commit_safe.sh": "GIT_EDITOR=true 안전 커밋 (WSL nano hang 방지)",
    "export_v10.py": "v10c 5-head ONNX export (export_multidisease_v1.py 대체 금지)",
    "start_v10_train.sh": "v10/v10b/v10c 멀티태스크 훈련 — V10B/V10C env",
    "preprocess_all.py": "GL/AMD/MYO/Multi CLAHE+224 resized_cache 전처리",
    "partner_smoke.sh": "Partner API smoke — REGISTER → ANALYZE → FHIR",
    "api_smoke_local.sh": "로컬 API 엔드포인트 smoke 테스트",
    "platform_regression_smoke.sh": "플랫폼 회귀 smoke (MEDI + compose)",
    "add_test_history.py": "tests/scripts 파일 히스토리 docstring 자동 추가",
}

SKIP_DIRS = {"__pycache__", "shared-libraries", "sl-ci", "training-remote"}


def _purpose(name: str) -> str:
    if name in PURPOSES:
        return PURPOSES[name]
    if name.startswith("test_"):
        topic = name.removeprefix("test_").replace("_", " ")
        return f"{topic} 단위·통합 테스트"
    return f"{name} 실행 스크립트"


def _has_history(text: str) -> bool:
    return "히스토리:" in text[:800]


def _py_block(name: str) -> str:
    purpose = _purpose(name)
    return (
        f'"""\n'
        f"파일명: {name}\n"
        f"목적: {purpose}\n"
        f"히스토리:\n"
        f"  {TODAY} - 현재 상태 문서화 + 히스토리 추가\n"
        f'"""\n'
    )


def _sh_block(name: str) -> str:
    purpose = _purpose(name)
    return (
        f"# =============================================================\n"
        f"# 파일명: {name}\n"
        f"# 목적: {purpose}\n"
        f"# 히스토리:\n"
        f"#   {TODAY} - 현재 상태 문서화 + 히스토리 추가\n"
        f"# =============================================================\n"
    )


def _merge_py_history(existing: str, name: str) -> str:
    entry = f"  {TODAY} - 현재 상태 문서화 + 히스토리 추가"
    if entry in existing:
        return existing
    if _has_history(existing):
        return re.sub(
            r"(히스토리:\n)",
            rf"\1{entry}\n",
            existing,
            count=1,
        )
    return _py_block(name) + existing.lstrip("\n")


def _merge_sh_history(existing: str, name: str) -> str:
    entry = f"#   {TODAY} - 현재 상태 문서화 + 히스토리 추가"
    if entry in existing:
        return existing
    if _has_history(existing):
        lines = existing.splitlines()
        out: list[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.strip() == "# 히스토리:":
                out.append(entry)
                inserted = True
        return "\n".join(out) + ("\n" if existing.endswith("\n") else "")
    block = _sh_block(name)
    if existing.startswith("#!"):
        first, rest = existing.split("\n", 1)
        return first + "\n" + block + rest
    return block + existing


def process_file(path: Path) -> bool:
    name = path.name
    text = path.read_text(encoding="utf-8")
    if _has_history(text) and f"{TODAY} - 현재 상태 문서화" in text[:1200]:
        return False

    future_m = re.match(r"^(from __future__ import annotations\n)", text)
    if future_m and not text.startswith('"""'):
        new_text = _py_block(name) + text
    elif text.startswith('"""'):
        end = text.find('"""', 3)
        if end == -1:
            return False
        doc = text[: end + 3]
        rest = text[end + 3 :].lstrip("\n")
        if _has_history(doc):
            new_doc = doc if f"{TODAY}" in doc else _merge_py_history(doc, name)
        else:
            inner = doc[3:-3].strip()
            purpose = _purpose(name)
            new_doc = (
                f'"""\n파일명: {name}\n목적: {purpose}\n히스토리:\n'
                f"  {TODAY} - 현재 상태 문서화 + 히스토리 추가\n\n{inner}\n\"\"\""
            )
        new_text = new_doc + "\n" + rest
    elif path.suffix == ".py":
        new_text = _py_block(name) + text
    elif path.suffix == ".sh":
        new_text = _merge_sh_history(text, name)
    else:
        return False
    if new_text != text:
        path.write_text(new_text, encoding="utf-8", newline="\n")
        return True
    return False


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv[1:] or ["tests"])]
    changed = 0
    for root in roots:
        if root.is_file():
            files = [root]
        else:
            files = sorted(
                p
                for p in root.rglob("*")
                if p.suffix in {".py", ".sh"}
                and not any(part in SKIP_DIRS for part in p.parts)
            )
        for fp in files:
            if process_file(fp):
                print(f"updated: {fp}")
                changed += 1
    print(f"done: {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
