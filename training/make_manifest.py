#!/usr/bin/env python3
"""추가 적응증 데이터셋 → 통합 manifest JSON 생성.

예:
  python training/make_manifest.py \\
    --data-root ~/workspace/dataset \\
    --sources refuge,airogs,adam,odir \\
    --output training/manifests/multi_indication.json
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def load_refuge(data_root: Path) -> list[dict]:
    """
    REFUGE: 1,200장
    라벨: glaucoma(1)/normal(0) — Glaucoma 폴더명 또는 CSV 기준
    태스크: glaucoma
    """
    base = data_root / "REFUGE_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for split_dir in ("Training400", "Validation400", "Test400"):
        split_path = base / split_dir
        if not split_path.is_dir():
            continue
        for img in split_path.rglob("*.jpg"):
            parent_name = img.parent.name.lower()
            if "glaucoma" in parent_name:
                label = 1
            elif "normal" in parent_name:
                label = 0
            else:
                label = 1 if "g" in img.stem.lower() else 0
            samples.append(
                {
                    "path": str(img.relative_to(data_root)),
                    "glaucoma_grade": label,
                    "source": "refuge",
                    "task": "glaucoma",
                }
            )
    return samples


def load_airogs(data_root: Path) -> list[dict]:
    """
    AIROGS: 101,442장
    라벨: RG(1)/NRG(0)
    태스크: glaucoma
    """
    csv_path = data_root / "AIROGS_raw" / "train_labels.csv"
    img_dir = data_root / "AIROGS_raw" / "images"
    samples: list[dict] = []
    if not csv_path.is_file():
        return samples

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = img_dir / f"{row['challenge_id']}.jpg"
            if img.is_file():
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "glaucoma_grade": 1 if row.get("class", "").upper() == "RG" else 0,
                        "source": "airogs",
                        "task": "glaucoma",
                    }
                )
    return samples


def load_adam_amd(data_root: Path) -> list[dict]:
    """
    ADAM: 1,200장
    라벨: AMD(1)/non-AMD(0)
    태스크: amd
    """
    base = data_root / "ADAM_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for label, folder in ((1, "AMD"), (0, "Non-AMD")):
        folder_path = base / folder
        if not folder_path.is_dir():
            continue
        for img in folder_path.glob("*.jpg"):
            samples.append(
                {
                    "path": str(img.relative_to(data_root)),
                    "amd_grade": label,
                    "source": "adam",
                    "task": "amd",
                }
            )
    return samples


def load_odir(data_root: Path) -> list[dict]:
    """
    ODIR-2019: 10,000장
    8개 질환 동시 라벨
    태스크: multi
    """
    csv_path = data_root / "ODIR2019_raw" / "labels.csv"
    img_dir = data_root / "ODIR2019_raw" / "images"
    samples: list[dict] = []
    if not csv_path.is_file():
        return samples

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filename = row.get("filename") or row.get("Left-Fundus") or row.get("Right-Fundus")
            if not filename:
                continue
            img = img_dir / filename
            if img.is_file():
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "dr_grade": int(row.get("DR", row.get("N", 0)) or 0),
                        "glaucoma_grade": int(row.get("G", 0) or 0),
                        "amd_grade": int(row.get("AMD", 0) or 0),
                        "source": "odir",
                        "task": "multi",
                    }
                )
    return samples


def _first_existing_dir(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.is_dir():
            return path
    return None


def _parse_glaucoma_label(raw: str | int | float | None) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"1", "1.0", "true", "yes", "g", "glaucoma", "rg", "positive", "pos"}:
        return 1
    if text in {"0", "0.0", "false", "no", "n", "normal", "nrg", "negative", "neg"}:
        return 0
    try:
        value = int(float(text))
        if value in (0, 1):
            return value
    except ValueError:
        pass
    return None


def _glaucoma_sample(data_root: Path, img: Path, label: int, source: str) -> dict:
    return {
        "path": str(img.relative_to(data_root)),
        "glaucoma_grade": label,
        "label": label,
        "source": source,
        "task": "glaucoma",
    }


def load_g1020(data_root: Path) -> list[dict]:
    """
    G1020: G1020/G1020.csv + G1020/Images/*.jpg
    라벨: CSV glaucoma 컬럼 (0/1)
    경로: Glaucoma_raw/G1020 (arnavjain1/glaucoma-datasets)
    """
    base = _first_existing_dir(
        [
            data_root / "Glaucoma_raw" / "G1020",
            data_root / "G1020_raw" / "G1020",
            data_root / "G1020",
        ]
    )
    if base is None:
        return []

    csv_path = base / "G1020.csv"
    if not csv_path.is_file():
        for alt in ("g1020.csv", "labels.csv"):
            candidate = base / alt
            if candidate.is_file():
                csv_path = candidate
                break
        else:
            return []

    img_dir = base / "Images"
    if not img_dir.is_dir():
        img_dir = base / "images"

    label_keys = ("glaucoma", "Glaucoma", "label", "Label", "class", "Class", "diagnosis")
    name_keys = ("image", "Image", "filename", "Filename", "file", "name", "img", "path")

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        fields = {c.lower(): c for c in reader.fieldnames}
        label_col = next((fields[k.lower()] for k in label_keys if k.lower() in fields), None)
        name_col = next((fields[k.lower()] for k in name_keys if k.lower() in fields), None)
        if label_col is None or name_col is None:
            return samples

        for row in reader:
            label = _parse_glaucoma_label(row.get(label_col))
            if label is None:
                continue
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            stem = Path(name).stem
            img = None
            for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ""):
                candidate = img_dir / (name if ext == "" else stem + ext)
                if candidate.is_file():
                    img = candidate
                    break
            if img is None and img_dir.is_dir():
                matches = list(img_dir.glob(f"{stem}.*"))
                img = matches[0] if matches else None
            if img is not None:
                samples.append(_glaucoma_sample(data_root, img, label, "g1020"))
    return samples


def load_refuge2(data_root: Path) -> list[dict]:
    """
    REFUGE2: train/val/test + images/ + 라벨(CSV 또는 Glaucoma/Normal 폴더)
    경로: Glaucoma_raw/REFUGE2
    """
    base = _first_existing_dir(
        [
            data_root / "Glaucoma_raw" / "REFUGE2",
            data_root / "REFUGE2_raw",
            data_root / "REFUGE2",
        ]
    )
    if base is None:
        return []

    samples: list[dict] = []
    split_names = ("train", "val", "test", "Train", "Val", "Test", "training", "validation")

    for split in split_names:
        split_dir = base / split
        if not split_dir.is_dir():
            continue

        for csv_name in (
            "labels.csv",
            "label.csv",
            "REFUGE2.csv",
            f"{split}_labels.csv",
            "index.csv",
        ):
            csv_path = split_dir / csv_name
            if not csv_path.is_file():
                continue
            img_dir = split_dir / "images"
            if not img_dir.is_dir():
                img_dir = split_dir / "Images"
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue
                fields = {c.lower(): c for c in reader.fieldnames}
                label_col = next(
                    (fields[k] for k in ("glaucoma", "label", "class", "diagnosis") if k in fields),
                    None,
                )
                name_col = next(
                    (fields[k] for k in ("image", "filename", "file", "name", "img") if k in fields),
                    None,
                )
                if label_col is None or name_col is None:
                    continue
                for row in reader:
                    label = _parse_glaucoma_label(row.get(label_col))
                    if label is None:
                        continue
                    name = (row.get(name_col) or "").strip()
                    if not name:
                        continue
                    img = img_dir / name
                    if not img.is_file():
                        img = img_dir / Path(name).name
                    if img.is_file():
                        samples.append(_glaucoma_sample(data_root, img, label, "refuge2"))

        for img_root_name in ("images", "Images"):
            img_root = split_dir / img_root_name
            if not img_root.is_dir():
                continue
            for sub, label in (("glaucoma", 1), ("normal", 0), ("Glaucoma", 1), ("Normal", 0)):
                folder = img_root / sub
                if not folder.is_dir():
                    continue
                for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG"):
                    for img in folder.glob(ext):
                        samples.append(_glaucoma_sample(data_root, img, label, "refuge2"))

    if samples:
        return samples

    for sub, label in (("glaucoma", 1), ("normal", 0), ("Glaucoma", 1), ("Normal", 0)):
        folder = base / sub
        if folder.is_dir():
            for ext in ("*.jpg", "*.jpeg", "*.png"):
                for img in folder.rglob(ext):
                    samples.append(_glaucoma_sample(data_root, img, label, "refuge2"))
    return samples


def build_glaucoma_manifest(
    dataset_root: Path,
    output_path: Path,
    *,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    """G1020 + REFUGE2(존재 시) → glaucoma_v1 manifest."""
    data_root = dataset_root.expanduser().resolve()
    loaders = (("g1020", load_g1020), ("refuge2", load_refuge2))
    all_samples: list[dict] = []
    counts: dict[str, int] = {}
    for name, loader in loaders:
        loaded = loader(data_root)
        counts[name] = len(loaded)
        all_samples.extend(loaded)

    seen_paths: set[str] = set()
    deduped: list[dict] = []
    for sample in all_samples:
        key = sample["path"]
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped.append(sample)
    all_samples = deduped

    train, val, test = split_samples(
        all_samples,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )
    pos = sum(1 for s in all_samples if int(s.get("glaucoma_grade", s.get("label", 0))) == 1)
    neg = len(all_samples) - pos

    manifest = {
        "data_dir": str(data_root),
        "task": "glaucoma",
        "version": 1,
        "sources": counts,
        "total": len(all_samples),
        "stats": {
            "total": len(all_samples),
            "glaucoma": pos,
            "normal": neg,
            "train": len(train),
            "val": len(val),
            "test": len(test),
        },
        "train": train,
        "val": val,
        "test": test,
    }

    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} total={len(all_samples)} glaucoma={pos} normal={neg} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )
    return manifest


def load_brazil_glaucoma(data_root: Path) -> list[dict]:
    """Brazil Glaucoma 공개 데이터 (논문/ Mendeley)."""
    base = data_root / "BrazilGlaucoma_raw"
    samples: list[dict] = []
    if not base.is_dir():
        return samples

    for label, folder in ((0, "normal"), (1, "glaucoma")):
        folder_path = base / folder
        if not folder_path.is_dir():
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            for img in folder_path.glob(ext):
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "glaucoma_grade": label,
                        "source": "brazil_glaucoma",
                        "task": "glaucoma",
                    }
                )
    return samples


LOADERS = {
    "refuge": load_refuge,
    "refuge2": load_refuge2,
    "g1020": load_g1020,
    "airogs": load_airogs,
    "adam": load_adam_amd,
    "odir": load_odir,
    "brazil": load_brazil_glaucoma,
}


def split_samples(
    samples: list[dict],
    *,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    rng = random.Random(seed)
    shuffled = samples[:]
    rng.shuffle(shuffled)
    n = len(shuffled)
    n_test = int(n * test_ratio)
    n_val = int(n * val_ratio)
    test = shuffled[:n_test]
    val = shuffled[n_test : n_test + n_val]
    train = shuffled[n_test + n_val :]
    return train, val, test


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-indication manifest")
    parser.add_argument("--data-root", type=Path, required=True, help="~/workspace/dataset")
    parser.add_argument(
        "--task",
        choices=("multi", "glaucoma"),
        default="multi",
        help="glaucoma: G1020+REFUGE2 전용 manifest",
    )
    parser.add_argument(
        "--sources",
        default="refuge,brazil,adam,odir",
        help="쉼표 구분: refuge,refuge2,g1020,airogs,adam,odir,brazil",
    )
    parser.add_argument("--output", type=Path, default=Path("training/manifests/multi_indication.json"))
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()

    if args.task == "glaucoma":
        build_glaucoma_manifest(
            data_root,
            args.output,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        return

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    all_samples: list[dict] = []
    counts: dict[str, int] = {}
    for name in sources:
        loader = LOADERS.get(name)
        if loader is None:
            raise SystemExit(f"unknown source={name!r}; choose from {sorted(LOADERS)}")
        loaded = loader(data_root)
        counts[name] = len(loaded)
        all_samples.extend(loaded)

    train, val, test = split_samples(
        all_samples,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    manifest = {
        "data_dir": str(data_root),
        "sources": counts,
        "train": train,
        "val": val,
        "test": test,
    }

    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {output} total={len(all_samples)} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )


if __name__ == "__main__":
    main()
