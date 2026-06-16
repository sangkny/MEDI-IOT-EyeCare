#!/usr/bin/env python3
"""
파일명: build_v10f_manifest.py
목적: unified_v10.json 기반 경로를 resized_cache → v2_cache 로 교체
      extra2 미포함 (순수 v2 전처리 효과 검증)
히스토리:
  2026-06-14 - 최초 작성 (Option B: v2_cache only)

로직:
  1) unified_v10.json 로드
  2) 각 샘플 경로에서 resized_cache → v2_cache 로 교체
     - /data_dr/resized_cache/... → /data_dr/v2_cache/...
     - resized_cache/...          → v2_cache/...
  3) v2_cache 파일 존재 확인
     - 존재: 경로 교체
     - 없음: 원본 resized_cache 유지 (fallback)
  4) 통계 출력: 교체된 샘플 수 / 총 샘플 수, v2_cache 비율

실행 (GPU, Docker):
  docker run --rm --entrypoint bash \
    -v ~/workspace/dataset:/dataset \
    -v ~/workspace/.../data:/data_dr \
    -v ~/workspace/.../MEDI-IOT-EyeCare:/workspace \
    medi-train:gpu -c '
      python3 /workspace/scripts/build_v10f_manifest.py
    '
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _rewrite_resized_to_v2(path: str) -> str:
    key = path.replace("\\", "/")
    key = key.replace("/data_dr/resized_cache/", "/data_dr/v2_cache/")
    key = key.replace("resized_cache/", "v2_cache/")
    return key


def _exists_in_mounts(*, rewritten: str, data_dir: str, dr_data_dir: str) -> bool:
    """
    훈련 컨테이너 기준 존재 체크.
    - 절대 경로(/data_dr, /dataset)는 그대로 확인
    - 상대 경로는 data_dir/dr_data_dir에 붙여 두 군데 모두 탐색 (fallback)
    """
    p = rewritten.replace("\\", "/")
    if p.startswith("/data_dr/") or p.startswith("/dataset/"):
        return Path(p).is_file()

    candidates = [
        Path(data_dir) / p,
        Path(dr_data_dir) / p,
    ]
    return any(c.is_file() for c in candidates)


def build_v10f(
    base: dict,
    *,
    data_dir: str = "/dataset",
    dr_data_dir: str = "/data_dr",
) -> tuple[dict, dict]:
    samples_in: list[dict] = list(base.get("samples") or [])

    replaced = 0
    kept = 0
    missing = 0
    by_prefix = Counter()

    samples_out: list[dict] = []
    for s in samples_in:
        orig = str(s.get("path") or "")
        if not orig:
            samples_out.append(s)
            kept += 1
            by_prefix["empty"] += 1
            continue

        rewritten = _rewrite_resized_to_v2(orig)
        if rewritten != orig and _exists_in_mounts(rewritten=rewritten, data_dir=data_dir, dr_data_dir=dr_data_dir):
            out = dict(s)
            out["path"] = rewritten
            samples_out.append(out)
            replaced += 1
            by_prefix["replaced"] += 1
        else:
            samples_out.append(s)
            kept += 1
            if rewritten != orig:
                missing += 1
                by_prefix["missing_v2_cache"] += 1
            else:
                by_prefix["no_resized_cache"] += 1

    out = dict(base)
    out["task"] = "v10f"
    out["sources"] = {
        **(base.get("sources") or {}),
        "base_manifest": "unified_v10.json",
        "rewrite": "resized_cache -> v2_cache (fallback keep resized_cache if missing)",
    }
    out["samples"] = samples_out

    total = len(samples_in)
    stats = {
        "total": total,
        "replaced": replaced,
        "kept": kept,
        "missing_v2_cache": missing,
        "v2_cache_ratio": (replaced / total) if total else 0.0,
        "by_prefix": dict(by_prefix),
    }
    return out, stats


def main() -> None:
    p = argparse.ArgumentParser(description="Build unified_v10f.json (v2_cache only, extra2 excluded)")
    p.add_argument("--base", type=Path, default=ROOT / "training/manifests/unified_v10.json")
    p.add_argument("--output", type=Path, default=ROOT / "training/manifests/unified_v10f.json")
    p.add_argument("--data-dir", type=str, default="/dataset")
    p.add_argument("--dr-data-dir", type=str, default="/data_dr")
    args = p.parse_args()

    base_path = args.base if args.base.is_absolute() else ROOT / args.base
    if not base_path.is_file():
        raise SystemExit(f"FAIL: base manifest missing: {base_path}")

    base = _load_json(base_path)
    manifest, st = build_v10f(base, data_dir=args.data_dir, dr_data_dir=args.dr_data_dir)

    out_path = args.output if args.output.is_absolute() else ROOT / args.output
    _dump_json(out_path, manifest)

    total = st["total"]
    replaced = st["replaced"]
    ratio = st["v2_cache_ratio"] * 100.0
    print(f"v10f: replaced={replaced} / total={total} (v2_cache ratio={ratio:.1f}%)")
    if st["missing_v2_cache"]:
        print(f"warn: missing_v2_cache={st['missing_v2_cache']} (fallback kept resized_cache)")
    print(f"OK → {out_path}")


if __name__ == "__main__":
    main()

