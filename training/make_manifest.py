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


def load_refuge(
    data_root: Path,
    *,
    extra_root: Path | None = None,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    REFUGE (glaucoma-datasets): train/val/test + index.json
    JSON: {idx: {ImgName, Label, ...}} · 이미지: {split}/Images/{ImgName}
    """
    base = _first_existing_dir(
        [
            data_root / "REFUGE",
            data_root / "Glaucoma_raw" / "REFUGE",
            data_root / "REFUGE_raw",
        ]
    )
    if base is None:
        return []

    path_root = manifest_root or data_root
    samples: list[dict] = []
    for split in ("train", "val", "test"):
        split_dir = base / split
        index_path = split_dir / "index.json"
        if not index_path.is_file():
            continue
        img_dir = split_dir / "Images"
        if not img_dir.is_dir():
            img_dir = split_dir / "images"
        entries = json.loads(index_path.read_text(encoding="utf-8"))
        if isinstance(entries, dict):
            rows = entries.values()
        elif isinstance(entries, list):
            rows = entries
        else:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = (row.get("ImgName") or row.get("imgname") or row.get("filename") or "").strip()
            label = _parse_glaucoma_label(row.get("Label", row.get("label")))
            if not name or label is None:
                continue
            img = img_dir / name
            if not img.is_file():
                stem = Path(name).stem
                for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ""):
                    candidate = img_dir / (name if ext == "" else stem + ext)
                    if candidate.is_file():
                        img = candidate
                        break
            if img.is_file():
                samples.append(_glaucoma_sample(path_root, img, label, "refuge"))

    if samples:
        return samples

    # 레거시: REFUGE_raw/Training400 … 폴더명 기반
    legacy = data_root / "REFUGE_raw"
    if not legacy.is_dir():
        return samples
    for split_dir in ("Training400", "Validation400", "Test400"):
        split_path = legacy / split_dir
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
            samples.append(_glaucoma_sample(path_root, img, label, "refuge"))
    return samples


def _airogs_light_dirs(data_root: Path, extra_root: Path | None) -> list[Path]:
    names = (
        "eyepac-light-v2-512-jpg",
        "AIROGS-light-v2-512-jpg",
        "airogs-light-v2-512-jpg",
    )
    candidates: list[Path] = []
    for root in (extra_root, data_root):
        if root is None:
            continue
        for name in names:
            candidates.append(root / "airogs" / name)
            candidates.append(root / "AIROGS" / name)
            candidates.append(root / name)
    return candidates


def _load_airogs_folder(base: Path, manifest_root: Path) -> list[dict]:
    """AIROGS-light-v2: train|val/{RG,NRG}/*.jpg — RG=1, NRG=0."""
    samples: list[dict] = []
    for split in ("train", "val", "test"):
        split_dir = base / split
        if not split_dir.is_dir():
            continue
        for folder_name, label in (("RG", 1), ("NRG", 0)):
            folder = split_dir / folder_name
            if not folder.is_dir():
                continue
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG"):
                for img in folder.glob(ext):
                    sample = _glaucoma_sample(manifest_root, img, label, "airogs")
                    sample["split"] = split
                    samples.append(sample)
    return samples


def load_airogs(
    data_root: Path,
    *,
    extra_root: Path | None = None,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    AIROGS-light-v2 (폴더): train|val/{RG,NRG} — RG=1, NRG=0
    레거시 CSV: AIROGS_raw/train_labels.csv
    """
    root = manifest_root or data_root
    for base in _airogs_light_dirs(data_root, extra_root):
        if base.is_dir():
            loaded = _load_airogs_folder(base, root)
            if loaded:
                return loaded

    csv_path = data_root / "AIROGS_raw" / "train_labels.csv"
    img_dir = data_root / "AIROGS_raw" / "images"
    samples: list[dict] = []
    if not csv_path.is_file():
        return samples

    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            img = img_dir / f"{row['challenge_id']}.jpg"
            if img.is_file():
                label = 1 if row.get("class", "").upper() == "RG" else 0
                samples.append(_glaucoma_sample(root, img, label, "airogs"))
    return samples


def load_rimone(
    data_root: Path,
    *,
    extra_root: Path | None = None,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    RIM-ONE-DL (partitioned_randomly):
      training_set/{glaucoma,normal} → split=train
      test_set/{glaucoma,normal} → split=test
    """
    root = manifest_root or data_root
    base = _first_existing_dir(
        [
            *((
                extra_root / "rimone" / "RIM-ONE_DL_images" / "partitioned_randomly",
                extra_root / "RIM-ONE" / "RIM-ONE_DL_images" / "partitioned_randomly",
            )
            if extra_root
            else ()),
            data_root / "Glaucoma_extra" / "rimone" / "RIM-ONE_DL_images" / "partitioned_randomly",
            data_root / "rimone" / "RIM-ONE_DL_images" / "partitioned_randomly",
        ]
    )
    if base is None:
        return []

    samples: list[dict] = []
    split_map = (
        ("training_set", "train"),
        ("test_set", "test"),
        ("validation_set", "val"),
    )
    for folder_name, split_name in split_map:
        split_dir = base / folder_name
        if not split_dir.is_dir():
            continue
        for sub_name, label in (
            ("glaucoma", 1),
            ("normal", 0),
            ("Glaucoma", 1),
            ("Normal", 0),
        ):
            folder = split_dir / sub_name
            if not folder.is_dir():
                continue
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.bmp"):
                for img in folder.glob(ext):
                    sample = _glaucoma_sample(root, img, label, "rimone")
                    sample["split"] = split_name
                    samples.append(sample)
    return samples


def load_adam_amd(data_root: Path) -> list[dict]:
    """
    ADAM (Age-related Macular Degeneration): ~1,200장
    경로 A: ADAM/training/images/ + labels.csv (AMD=1, normal=0)
    경로 B: ADAM_raw/{AMD,Non-AMD}/*.jpg (legacy)
    """
    samples: list[dict] = []

    def _amd_sample(root: Path, img: Path, label: int, source: str = "adam") -> dict:
        return {
            "path": str(img.relative_to(data_root)),
            "amd_grade": label,
            "label": label,
            "source": source,
            "task": "amd",
        }

    adam_base = _first_existing_dir(
        [
            data_root / "AMD_raw" / "ADAM",
            data_root / "ADAM",
            data_root / "ADAM_raw",
        ]
    )
    if adam_base is not None:
        for csv_name in ("labels.csv", "label.csv", "training_labels.csv"):
            csv_path = adam_base / csv_name
            if not csv_path.is_file():
                training = adam_base / "training"
                csv_path = training / csv_name if training.is_dir() else csv_path
            if not csv_path.is_file():
                continue
            img_dir = adam_base / "training" / "images"
            if not img_dir.is_dir():
                img_dir = adam_base / "images"
            if not img_dir.is_dir():
                img_dir = adam_base
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue
                fields = {c.lower(): c for c in reader.fieldnames}
                label_col = next(
                    (fields[k] for k in ("amd", "label", "class", "diagnosis") if k in fields),
                    None,
                )
                name_col = next(
                    (fields[k] for k in ("image", "filename", "file", "name", "img") if k in fields),
                    None,
                )
                if label_col is None or name_col is None:
                    continue
                for row in reader:
                    raw_label = row.get(label_col)
                    text = str(raw_label or "").strip().lower()
                    if text in {"1", "amd", "positive", "yes", "true"}:
                        label = 1
                    elif text in {"0", "normal", "non-amd", "negative", "no", "false"}:
                        label = 0
                    else:
                        try:
                            label = int(float(text))
                        except ValueError:
                            continue
                    name = (row.get(name_col) or "").strip()
                    if not name:
                        continue
                    img = img_dir / name
                    if not img.is_file():
                        img = img_dir / Path(name).name
                    if img.is_file():
                        samples.append(_amd_sample(data_root, img, label))
            if samples:
                return samples

        for label, folder in ((1, "AMD"), (0, "Non-AMD"), (1, "amd"), (0, "normal")):
            folder_path = adam_base / folder
            if not folder_path.is_dir():
                continue
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG"):
                for img in folder_path.rglob(ext):
                    samples.append(_amd_sample(data_root, img, label))
        if samples:
            return samples

    return samples


def load_adam(data_root: Path) -> list[dict]:
    """ADAM loader alias (AMD Phase 2)."""
    return load_adam_amd(data_root)


def _amd_sample(
    path_root: Path,
    img: Path,
    label: int,
    source: str,
    *,
    split: str | None = None,
) -> dict:
    sample = {
        "path": str(img.relative_to(path_root)),
        "amd_grade": label,
        "label": label,
        "source": source,
        "task": "amd",
    }
    if split:
        sample["split"] = split
    return sample


def _myopia_sample(
    path_root: Path,
    img: Path,
    label: int,
    source: str,
    *,
    split: str | None = None,
) -> dict:
    sample = {
        "path": str(img.relative_to(path_root)),
        "myopia_grade": label,
        "label": label,
        "source": source,
        "task": "myopia",
    }
    if split:
        sample["split"] = split
    return sample


def _find_amdnet23_dataset(base: Path) -> Path | None:
    for candidate in (
        base / "AMDNet23 Dataset",
        base / "AMDNet23" / "AMDNet23 Dataset",
    ):
        if candidate.is_dir() and (candidate / "train").is_dir():
            return candidate
    for path in base.rglob("AMDNet23 Dataset"):
        if path.is_dir() and (path / "train").is_dir():
            return path
    return None


def _find_odir_root(base: Path) -> Path | None:
    return _first_existing_dir(
        [
            base / "ODIR",
            base / "Multidisease_raw" / "ODIR",
            base,
        ]
    )


def _find_odir_image_dir(odir_base: Path) -> Path | None:
    return _first_existing_dir(
        [
            odir_base / "preprocessed_images",
            odir_base / "training images",
            odir_base / "training_images",
            odir_base / "images",
            odir_base / "Images",
        ]
    )


def _odir_row_filenames(row: dict) -> list[str]:
    names: list[str] = []
    for key in (
        "filename",
        "Filename",
        "Image",
        "ID",
        "Left-Fundus",
        "Right-Fundus",
        "left",
        "right",
    ):
        raw = (row.get(key) or "").strip()
        if raw and raw.lower() not in {"nan", "none"}:
            names.append(Path(raw).name)
    return names


def _odir_fundus_filenames(row: dict) -> list[str]:
    """ODIR 좌/우 안저 파일명만 (ID·filename 중복 열거 방지)."""
    names: list[str] = []
    seen: set[str] = set()
    for key in ("Left-Fundus", "Right-Fundus", "left", "right"):
        raw = (row.get(key) or "").strip()
        if not raw or raw.lower() in {"nan", "none"}:
            continue
        name = Path(raw).name
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    if names:
        return names
    for key in ("filename", "Filename", "Image"):
        raw = (row.get(key) or "").strip()
        if raw and raw.lower() not in {"nan", "none"}:
            return [Path(raw).name]
    return []


def _odir_one_hot_flag(row: dict, fieldnames: list[str], col: str) -> int | None:
    """ODIR full_df 단일 플래그 (N, M, D, …) — 정확한 컬럼명만."""
    key_map = {name.upper(): name for name in fieldnames}
    col_key = key_map.get(col.upper())
    if col_key is None:
        return None
    raw = row.get(col_key)
    if raw in (None, ""):
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return None


def _resolve_odir_image(img_dir: Path, filename: str) -> Path | None:
    candidates = [img_dir / filename, img_dir / Path(filename).name]
    stem = Path(filename).stem
    for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG", ""):
        candidates.append(img_dir / (stem + ext if ext else filename))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _odir_binary(row: dict, *keys: str) -> int:
    for key in keys:
        raw = row.get(key)
        if raw in (None, ""):
            continue
        try:
            return int(float(raw))
        except ValueError:
            continue
    return 0


def load_amdnet23(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    AMDNet23: train|valid × {amd,normal,...}
    label: amd=1, normal=0 (cataract/diabetes 제외)
    """
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    dataset_root = _find_amdnet23_dataset(base)
    if dataset_root is None:
        return []

    samples: list[dict] = []
    for split_name in ("train", "valid", "val"):
        split_dir = dataset_root / split_name
        if not split_dir.is_dir():
            continue
        native_split = "train" if split_name == "train" else "val"
        for folder, label in (("amd", 1), ("AMD", 1), ("normal", 0), ("Normal", 0)):
            folder_path = split_dir / folder
            if not folder_path.is_dir():
                continue
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"):
                for img in folder_path.glob(ext):
                    samples.append(
                        _amd_sample(path_root, img, label, "amdnet23", split=native_split)
                    )
    return samples


def load_odir_amd(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """ODIR full_df — A=1(AMD), N=1 and A=0(normal)."""
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    odir_base = _find_odir_root(base)
    if odir_base is None:
        return []

    csv_path = odir_base / "full_df.csv"
    if not csv_path.is_file():
        for alt in ("labels.csv", "label.csv"):
            candidate = odir_base / alt
            if candidate.is_file():
                csv_path = candidate
                break
    img_dir = _find_odir_image_dir(odir_base)
    if not csv_path.is_file() or img_dir is None:
        return []

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        for row in reader:
            amd = _odir_binary(row, "A", "AMD", "amd")
            normal = _odir_binary(row, "N", "Normal", "normal")
            if amd == 1:
                label = 1
            elif normal == 1 and amd == 0:
                label = 0
            else:
                continue
            for filename in _odir_row_filenames(row):
                img = _resolve_odir_image(img_dir, filename)
                if img is not None:
                    samples.append(_amd_sample(path_root, img, label, "odir_amd"))
    return samples


def _find_rfmid_root(base: Path) -> Path | None:
    return _first_existing_dir(
        [
            base / "RFMiD",
            base / "Multidisease_raw" / "RFMiD",
            base,
        ]
    )


def _find_rfmid_training(base: Path) -> tuple[Path | None, Path | None]:
    rfmid_base = _find_rfmid_root(base)
    if rfmid_base is None:
        return None, None
    train_dir = _first_existing_dir(
        [
            rfmid_base / "Training_set",
            rfmid_base / "train",
            rfmid_base / "Train",
        ]
    )
    csv_candidates = [
        rfmid_base / "Training_set" / "RFMiD_Training_Labels.csv",
        rfmid_base / "RFMiD_Training_Labels.csv",
    ]
    if train_dir is not None:
        csv_candidates.append(train_dir / "RFMiD_Training_Labels.csv")
    csv_path = next((p for p in csv_candidates if p.is_file()), None)
    return train_dir, csv_path


def _resolve_rfmid_image(train_dir: Path, image_id: str) -> Path | None:
    stem = Path(image_id).stem
    for ext in (".png", ".jpg", ".jpeg", ".tif", ".PNG", ".JPG", ""):
        candidate = train_dir / (image_id if ext == "" else stem + ext)
        if candidate.is_file():
            return candidate
    return None


def load_rfmid_amd(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """RFMiD Training_set — ARMD=1(AMD), Disease_Risk=0 and ARMD=0(normal)."""
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    train_dir, csv_path = _find_rfmid_training(base)
    if train_dir is None or csv_path is None:
        return []

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        fields = {c.upper(): c for c in reader.fieldnames}
        id_col = fields.get("ID", reader.fieldnames[0])
        armd_col = fields.get("ARMD")
        risk_col = fields.get("DISEASE_RISK")
        for row in reader:
            if armd_col is None or risk_col is None:
                continue
            armd = _odir_binary(row, armd_col)
            risk = _odir_binary(row, risk_col)
            if armd == 1:
                label = 1
            elif risk == 0 and armd == 0:
                label = 0
            else:
                continue
            image_id = (row.get(id_col) or "").strip()
            if not image_id:
                continue
            img = _resolve_rfmid_image(train_dir, image_id)
            if img is not None:
                samples.append(_amd_sample(path_root, img, label, "rfmid_amd"))
    return samples


def load_odir_myopia(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """ODIR — M=1(myopia), N=1 and M=0(normal) only.

    다른 질환(D/G/C/A/…) 행은 제외. 좌/우 안저 각 1장씩만 포함.
    """
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    odir_base = _find_odir_root(base)
    if odir_base is None:
        return []

    csv_path = odir_base / "full_df.csv"
    if not csv_path.is_file():
        for alt in ("labels.csv", "label.csv"):
            candidate = odir_base / alt
            if candidate.is_file():
                csv_path = candidate
                break
    img_dir = _find_odir_image_dir(odir_base)
    if not csv_path.is_file() or img_dir is None:
        return []

    samples: list[dict] = []
    seen_paths: set[str] = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        fieldnames = list(reader.fieldnames)
        upper_cols = {name.upper() for name in fieldnames}
        if "M" not in upper_cols or "N" not in upper_cols:
            return samples
        for row in reader:
            m_flag = _odir_one_hot_flag(row, fieldnames, "M")
            n_flag = _odir_one_hot_flag(row, fieldnames, "N")
            if m_flag is None or n_flag is None:
                continue
            if m_flag == 1:
                label = 1
            elif n_flag == 1 and m_flag == 0:
                label = 0
            else:
                continue
            for filename in _odir_fundus_filenames(row):
                img = _resolve_odir_image(img_dir, filename)
                if img is None:
                    continue
                rel = str(img.relative_to(path_root))
                if rel in seen_paths:
                    continue
                seen_paths.add(rel)
                samples.append(_myopia_sample(path_root, img, label, "odir_myopia"))
    return samples


def load_rfmid_myopia(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """RFMiD — MYA=1(myopia), Disease_Risk=0 and MYA=0(normal) only."""
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    train_dir, csv_path = _find_rfmid_training(base)
    if train_dir is None or csv_path is None:
        return []

    samples: list[dict] = []
    seen_paths: set[str] = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        fields = {c.upper(): c for c in reader.fieldnames}
        id_col = fields.get("ID", reader.fieldnames[0])
        mya_col = fields.get("MYA")
        risk_col = fields.get("DISEASE_RISK")
        if mya_col is None or risk_col is None:
            return samples
        for row in reader:
            try:
                mya = int(float(row.get(mya_col) or 0))
                risk = int(float(row.get(risk_col) or 0))
            except ValueError:
                continue
            if mya == 1:
                label = 1
            elif risk == 0 and mya == 0:
                label = 0
            else:
                continue
            image_id = (row.get(id_col) or "").strip()
            if not image_id:
                continue
            img = _resolve_rfmid_image(train_dir, image_id)
            if img is None:
                continue
            rel = str(img.relative_to(path_root))
            if rel in seen_paths:
                continue
            seen_paths.add(rel)
            samples.append(_myopia_sample(path_root, img, label, "rfmid_myopia"))
    return samples


MULTIDISEASE_ODIR_KEYS = {
    "D": "dr",
    "G": "glaucoma",
    "C": "cataract",
    "A": "amd",
    "H": "htn",
    "M": "myopia",
    "O": "other",
    "N": "normal",
}

MULTIDISEASE_RFMID_KEYS = (
    "DR",
    "ARMD",
    "MH",
    "MYA",
    "BRVO",
    "DN",
    "HTN",
    "ODP",
    "ERM",
    "CRVO",
)


def load_odir_multidisease(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """ODIR 8-class multi-label (N,D,G,C,A,H,M,O)."""
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    odir_base = _find_odir_root(base)
    if odir_base is None:
        return []

    csv_path = odir_base / "full_df.csv"
    if not csv_path.is_file():
        return []
    img_dir = _find_odir_image_dir(odir_base)
    if img_dir is None:
        return []

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        for row in reader:
            labels = {
                name: _odir_binary(row, key, name, name.upper())
                for key, name in MULTIDISEASE_ODIR_KEYS.items()
            }
            for filename in _odir_row_filenames(row):
                img = _resolve_odir_image(img_dir, filename)
                if img is not None:
                    samples.append(
                        {
                            "path": str(img.relative_to(path_root)),
                            "source": "odir",
                            "task": "multidisease",
                            "labels": labels,
                        }
                    )
    return samples


def load_rfmid_multidisease(
    base_path: Path,
    *,
    manifest_root: Path | None = None,
) -> list[dict]:
    """RFMiD Training_set — CSV header 전체 질환 멀티레이블."""
    base = base_path.expanduser().resolve()
    path_root = manifest_root or base
    train_dir, csv_path = _find_rfmid_training(base)
    if train_dir is None or csv_path is None:
        return []

    skip_cols = {"ID", "Disease_Risk", "DISEASE_RISK"}
    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        id_col = reader.fieldnames[0]
        disease_cols = [c for c in reader.fieldnames if c.upper() not in skip_cols]
        for row in reader:
            image_id = (row.get(id_col) or "").strip()
            if not image_id:
                continue
            img = _resolve_rfmid_image(train_dir, image_id)
            if img is None:
                continue
            labels: dict[str, int] = {}
            for col in disease_cols:
                try:
                    labels[col.lower()] = int(float(row.get(col) or 0))
                except ValueError:
                    labels[col.lower()] = 0
            samples.append(
                {
                    "path": str(img.relative_to(path_root)),
                    "source": "rfmid",
                    "task": "multidisease",
                    "labels": labels,
                }
            )
    return samples


def load_palm(data_root: Path) -> list[dict]:
    """
    PALM (Pathological Myopia): ~1,200장
    PALM/training/images/ + labels.csv — myopia=1, normal=0
    """
    base = _first_existing_dir(
        [
            data_root / "Myopia_raw" / "PALM",
            data_root / "PALM",
            data_root / "PALM_raw",
        ]
    )
    samples: list[dict] = []
    if base is None:
        return samples

    for csv_name in ("labels.csv", "label.csv"):
        csv_path = base / csv_name
        training = base / "training"
        if not csv_path.is_file() and training.is_dir():
            csv_path = training / csv_name
        if not csv_path.is_file():
            continue
        img_dir = training / "images" if training.is_dir() else base / "images"
        if not img_dir.is_dir():
            img_dir = base
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue
            fields = {c.lower(): c for c in reader.fieldnames}
            label_col = next(
                (fields[k] for k in ("myopia", "label", "class", "pathological") if k in fields),
                None,
            )
            name_col = next(
                (fields[k] for k in ("image", "filename", "file", "name") if k in fields),
                None,
            )
            if label_col is None or name_col is None:
                continue
            for row in reader:
                text = str(row.get(label_col) or "").strip().lower()
                if text in {"1", "myopia", "pathological", "yes", "true", "positive"}:
                    label = 1
                elif text in {"0", "normal", "no", "false", "negative"}:
                    label = 0
                else:
                    try:
                        label = int(float(text))
                    except ValueError:
                        continue
                name = (row.get(name_col) or "").strip()
                if not name:
                    continue
                img = img_dir / name
                if img.is_file():
                    samples.append(
                        {
                            "path": str(img.relative_to(data_root)),
                            "myopia_grade": label,
                            "label": label,
                            "source": "palm",
                            "task": "myopia",
                        }
                    )
        if samples:
            return samples

    for label, folder in ((1, "myopia"), (0, "normal"), (1, "pathological")):
        folder_path = base / folder
        if not folder_path.is_dir():
            continue
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            for img in folder_path.rglob(ext):
                samples.append(
                    {
                        "path": str(img.relative_to(data_root)),
                        "myopia_grade": label,
                        "label": label,
                        "source": "palm",
                        "task": "myopia",
                    }
                )
    return samples


def load_rfmid(data_root: Path) -> list[dict]:
    """
    RFMiD 2.0: ~3,200장, 46질환
    RFMiD/train/ + RFMiD_Training_Labels.csv
    """
    base = _first_existing_dir(
        [
            data_root / "Multidisease_raw" / "RFMiD",
            data_root / "RFMiD",
            data_root / "RFMiD_raw",
        ]
    )
    samples: list[dict] = []
    if base is None:
        return samples

    csv_candidates = [
        base / "RFMiD_Training_Labels.csv",
        base / "labels.csv",
        base / "train" / "RFMiD_Training_Labels.csv",
    ]
    img_dirs = [base / "train", base / "Train", base / "images", base]
    csv_path = next((p for p in csv_candidates if p.is_file()), None)
    if csv_path is None:
        return samples

    img_dir = next((d for d in img_dirs if d.is_dir()), base)
    disease_cols = (
        "DR",
        "AMD",
        "MH",
        "MYA",
        "BRVO",
        "CRVO",
        "HTN",
        "ODP",
        "DN",
        "ARMD",
    )
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return samples
        fields = {c.upper(): c for c in reader.fieldnames}
        name_col = next(
            (
                fields[k]
                for k in ("ID", "IMAGE", "FILENAME", "FILE", "NAME")
                if k in fields
            ),
            reader.fieldnames[0],
        )
        for row in reader:
            name = (row.get(name_col) or "").strip()
            if not name:
                continue
            stem = Path(name).stem
            img = img_dir / name
            if not img.is_file():
                for ext in (".jpg", ".jpeg", ".png", ".tif", ""):
                    candidate = img_dir / (name if ext == "" else stem + ext)
                    if candidate.is_file():
                        img = candidate
                        break
            if not img.is_file():
                continue
            labels = {}
            for col in disease_cols:
                key = fields.get(col)
                if key and row.get(key) not in (None, ""):
                    try:
                        labels[col.lower()] = int(float(row[key]))
                    except ValueError:
                        labels[col.lower()] = 0
            samples.append(
                {
                    "path": str(img.relative_to(data_root)),
                    "source": "rfmid",
                    "task": "multidisease",
                    "labels": labels,
                }
            )
    return samples


def load_odir(data_root: Path) -> list[dict]:
    """
    ODIR-5K / ODIR-2019: ~10,000장, 8질환 (normal/DR/glaucoma/cataract/AMD/HTN/myopia/other)
    ODIR-5K/training images/ + labels.xlsx (또는 labels.csv)
    """
    bases = [
        data_root / "Multidisease_raw" / "ODIR",
        data_root / "ODIR-5K",
        data_root / "ODIR2019_raw",
        data_root / "odir",
    ]
    csv_candidates: list[Path] = []
    img_dirs: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        csv_candidates.extend(
            [
                base / "labels.csv",
                base / "label.csv",
                base / "full_df.csv",
            ]
        )
        img_dirs.extend(
            [
                base / "training images",
                base / "training_images",
                base / "images",
                base / "Images",
            ]
        )

    csv_path = next((p for p in csv_candidates if p.is_file()), None)
    img_dir = next((d for d in img_dirs if d.is_dir()), None)
    samples: list[dict] = []
    if csv_path is None or img_dir is None:
        return samples

    def _odir_row(row: dict, filename: str) -> dict:
        return {
            "path": str((img_dir / filename).relative_to(data_root)),
            "dr_grade": int(row.get("DR", row.get("N", 0)) or 0),
            "glaucoma_grade": int(row.get("G", row.get("Glaucoma", 0)) or 0),
            "amd_grade": int(row.get("AMD", 0) or 0),
            "myopia_grade": int(row.get("MYA", row.get("Myopia", 0)) or 0),
            "source": "odir",
            "task": "multi",
        }

    with csv_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            filename = (
                row.get("filename")
                or row.get("Left-Fundus")
                or row.get("Right-Fundus")
                or row.get("Image")
                or row.get("ID")
            )
            if not filename:
                continue
            img = img_dir / filename
            if not img.is_file():
                img = img_dir / Path(filename).name
            if img.is_file():
                samples.append(_odir_row(row, img.name))
    return samples


AMD_LOADERS = {
    "adam": load_adam_amd,
    "adam_amd": load_adam_amd,
    "amdnet23": load_amdnet23,
    "odir_amd": load_odir_amd,
    "rfmid_amd": load_rfmid_amd,
}

MYOPIA_LOADERS = {
    "palm": load_palm,
    "odir": load_odir,
    "odir_myopia": load_odir_myopia,
    "rfmid_myopia": load_rfmid_myopia,
}

MULTIDISEASE_LOADERS = {
    "rfmid": load_rfmid_multidisease,
    "odir": load_odir_multidisease,
}


def load_g1020(
    data_root: Path,
    *,
    extra_root: Path | None = None,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    G1020: G1020/G1020.csv — imageID, binaryLabels (0=normal, 1=glaucoma)
    이미지: G1020/Images/{imageID}
    """
    base = _first_existing_dir(
        [
            data_root / "G1020",
            data_root / "Glaucoma_raw" / "G1020",
            data_root / "G1020_raw" / "G1020",
        ]
    )
    if base is None:
        return []

    path_root = manifest_root or data_root
    csv_path = base / "G1020.csv"
    if not csv_path.is_file():
        return []

    img_dir = base / "Images"
    if not img_dir.is_dir():
        img_dir = base / "images"

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_id = (row.get("imageID") or row.get("ImageID") or row.get("image") or "").strip()
            label = _parse_glaucoma_label(
                row.get("binaryLabels", row.get("BinaryLabels", row.get("glaucoma")))
            )
            if not image_id or label is None:
                continue
            img = img_dir / image_id
            if not img.is_file():
                stem = Path(image_id).stem
                for ext in (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ""):
                    candidate = img_dir / (image_id if ext == "" else stem + ext)
                    if candidate.is_file():
                        img = candidate
                        break
            if img.is_file():
                samples.append(_glaucoma_sample(path_root, img, label, "g1020"))
    return samples


def load_origa(
    data_root: Path,
    *,
    extra_root: Path | None = None,
    manifest_root: Path | None = None,
) -> list[dict]:
    """
    ORIGA: ORIGA/OrigaList.csv — Filename, Glaucoma (0/1)
    이미지: ORIGA/Images/{Filename}
    """
    base = _first_existing_dir(
        [
            data_root / "ORIGA",
            data_root / "Glaucoma_raw" / "ORIGA",
            data_root / "ORIGA_raw",
        ]
    )
    if base is None:
        return []

    path_root = manifest_root or data_root
    csv_path = base / "OrigaList.csv"
    if not csv_path.is_file():
        return []

    img_dir = base / "Images"
    if not img_dir.is_dir():
        img_dir = base / "images"

    samples: list[dict] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = (row.get("Filename") or row.get("filename") or "").strip()
            label = _parse_glaucoma_label(row.get("Glaucoma", row.get("glaucoma")))
            if not filename or label is None:
                continue
            img = img_dir / filename
            if not img.is_file():
                stem = Path(filename).stem
                for ext in (".jpg", ".jpeg", ".png", ".tif", ".TIF", ""):
                    candidate = img_dir / (filename if ext == "" else stem + ext)
                    if candidate.is_file():
                        img = candidate
                        break
            if img.is_file():
                samples.append(_glaucoma_sample(path_root, img, label, "origa"))
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


GLAUCOMA_LOADERS: dict[str, object] = {
    "g1020": load_g1020,
    "refuge": load_refuge,
    "origa": load_origa,
    "airogs": load_airogs,
    "rimone": load_rimone,
}


def _resolve_manifest_root(primary: Path, extra: Path | None) -> Path:
    primary = primary.expanduser().resolve()
    if extra is None:
        return primary
    extra = extra.expanduser().resolve()
    if primary.parent == extra.parent:
        return primary.parent
    return primary


def _assign_splits(
    samples: list[dict],
    *,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    preset_train: list[dict] = []
    preset_val: list[dict] = []
    preset_test: list[dict] = []
    unpreset: list[dict] = []

    for sample in samples:
        split = sample.get("split")
        if split == "train":
            preset_train.append(sample)
        elif split == "val":
            preset_val.append(sample)
        elif split == "test":
            preset_test.append(sample)
        else:
            unpreset.append(sample)

    train_u, val_u, test_u = split_samples(
        unpreset,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )
    train = preset_train + train_u
    val = preset_val + val_u
    test = preset_test + test_u
    for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
        for sample in chunk:
            sample["split"] = split_name
    return train, val, test


def build_glaucoma_manifest(
    dataset_root: Path,
    output_path: Path,
    *,
    extra_root: Path | None = None,
    sources: tuple[str, ...] | None = None,
    val_ratio: float = 0.10,
    test_ratio: float = 0.10,
    seed: int = 42,
    version: int = 1,
    unified_split: bool | None = None,
) -> dict:
    """Glaucoma manifest — v1: G1020+REFUGE+ORIGA · v2: +AIROGS+RIM-ONE.

    unified_split=True (v2 기본): 소스 native split 무시, 전체 셔플 후 train/val/test 재분리.
    """
    data_root = dataset_root.expanduser().resolve()
    extra = extra_root.expanduser().resolve() if extra_root else None
    manifest_root = _resolve_manifest_root(data_root, extra)
    source_names = sources or tuple(GLAUCOMA_LOADERS.keys())
    all_samples: list[dict] = []
    counts: dict[str, int] = {}
    for name in source_names:
        loader = GLAUCOMA_LOADERS.get(name)
        if loader is None:
            raise ValueError(f"unknown glaucoma source={name!r}; choose from {sorted(GLAUCOMA_LOADERS)}")
        loaded = loader(data_root, extra_root=extra, manifest_root=manifest_root)  # type: ignore[operator]
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

    use_unified = unified_split if unified_split is not None else (version >= 2 or extra is not None)
    if use_unified:
        for sample in all_samples:
            sample.pop("split", None)
        train, val, test = split_samples(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
            for sample in chunk:
                sample["split"] = split_name
    else:
        train, val, test = _assign_splits(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
    combined = train + val + test
    pos = sum(1 for s in combined if int(s.get("label", s.get("glaucoma_grade", 0))) == 1)
    neg = len(combined) - pos
    total = len(combined)
    pct_g = (pos / total * 100.0) if total else 0.0
    pct_n = (neg / total * 100.0) if total else 0.0

    manifest = {
        "data_dir": str(manifest_root),
        "task": "glaucoma",
        "version": version,
        "sources": counts,
        "total": total,
        "stats": {
            "total": total,
            "glaucoma": pos,
            "normal": neg,
            "glaucoma_pct": round(pct_g, 2),
            "normal_pct": round(pct_n, 2),
            "train": len(train),
            "val": len(val),
            "test": len(test),
        },
        "samples": combined,
        "train": train,
        "val": val,
        "test": test,
    }

    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} total={total} glaucoma={pos} ({pct_g:.1f}%) normal={neg} ({pct_n:.1f}%) "
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
    "origa": load_origa,
    "airogs": load_airogs,
    "adam": load_adam,
    "palm": load_palm,
    "rfmid": load_rfmid,
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


def _write_task_manifest(
    data_root: Path,
    output_path: Path,
    samples: list[dict],
    *,
    task: str,
    sources: dict[str, int],
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    train, val, test = split_samples(
        samples,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )
    manifest = {
        "data_dir": str(data_root),
        "task": task,
        "sources": sources,
        "total": len(samples),
        "train": train,
        "val": val,
        "test": test,
        "samples": train + val + test,
    }
    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} task={task} total={len(samples)} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={sources}"
    )
    return manifest


def build_amd_manifest(
    dataset_root: Path,
    output_path: Path,
    *,
    extra_root: Path | None = None,
    sources: tuple[str, ...] = ("amdnet23", "odir_amd", "rfmid_amd"),
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    unified_split: bool = True,
) -> dict:
    """AMD Phase 2 — AMDNet23 + ODIR + RFMiD (unified split)."""
    data_root = dataset_root.expanduser().resolve()
    extra = extra_root.expanduser().resolve() if extra_root else None
    manifest_root = _resolve_manifest_root(data_root, extra)
    all_samples: list[dict] = []
    counts: dict[str, int] = {}

    for name in sources:
        if name in ("adam", "adam_amd"):
            loaded = load_adam_amd(data_root)
            if manifest_root != data_root:
                for sample in loaded:
                    sample["path"] = str((data_root / sample["path"]).relative_to(manifest_root))
        elif name == "amdnet23":
            loaded = load_amdnet23(data_root, manifest_root=manifest_root)
        elif name == "odir_amd":
            src_root = extra or data_root
            loaded = load_odir_amd(src_root, manifest_root=manifest_root)
        elif name == "rfmid_amd":
            src_root = extra or data_root
            loaded = load_rfmid_amd(src_root, manifest_root=manifest_root)
        else:
            raise ValueError(f"unknown amd source={name!r}; choose from {sorted(AMD_LOADERS)}")
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

    if unified_split:
        for sample in all_samples:
            sample.pop("split", None)
        train, val, test = split_samples(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
            for sample in chunk:
                sample["split"] = split_name
    else:
        train, val, test = _assign_splits(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )

    combined = train + val + test
    pos = sum(1 for s in combined if int(s.get("label", s.get("amd_grade", 0))) == 1)
    neg = len(combined) - pos
    total = len(combined)

    manifest = {
        "data_dir": str(manifest_root),
        "task": "amd",
        "sources": counts,
        "total": total,
        "stats": {
            "total": total,
            "amd": pos,
            "normal": neg,
            "train": len(train),
            "val": len(val),
            "test": len(test),
        },
        "samples": combined,
        "train": train,
        "val": val,
        "test": test,
    }

    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} task=amd total={total} amd={pos} normal={neg} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )
    return manifest


def build_myopia_manifest(
    dataset_root: Path,
    output_path: Path,
    *,
    extra_root: Path | None = None,
    sources: tuple[str, ...] = ("palm",),
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    unified_split: bool = True,
) -> dict:
    """근시 Phase 3 — PALM (+ ODIR/RFMiD myopia subset)."""
    data_root = dataset_root.expanduser().resolve()
    extra = extra_root.expanduser().resolve() if extra_root else None
    manifest_root = _resolve_manifest_root(data_root, extra)
    all_samples: list[dict] = []
    counts: dict[str, int] = {}

    for name in sources:
        if name == "palm":
            loaded = load_palm(data_root)
            if manifest_root != data_root:
                for sample in loaded:
                    sample["path"] = str((data_root / sample["path"]).relative_to(manifest_root))
        elif name == "odir":
            src_root = extra or data_root
            loaded = load_odir(src_root)
        elif name == "odir_myopia":
            src_root = extra or data_root
            loaded = load_odir_myopia(src_root, manifest_root=manifest_root)
        elif name == "rfmid_myopia":
            src_root = extra or data_root
            loaded = load_rfmid_myopia(src_root, manifest_root=manifest_root)
        else:
            raise ValueError(f"unknown myopia source={name!r}; choose from {sorted(MYOPIA_LOADERS)}")
        counts[name] = len(loaded)
        all_samples.extend(loaded)

    if unified_split:
        for sample in all_samples:
            sample.pop("split", None)
        train, val, test = split_samples(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
            for sample in chunk:
                sample["split"] = split_name
    else:
        train, val, test = split_samples(
            all_samples,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            seed=seed,
        )
        for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
            for sample in chunk:
                sample["split"] = split_name

    combined = train + val + test
    manifest = {
        "data_dir": str(manifest_root),
        "task": "myopia",
        "sources": counts,
        "total": len(combined),
        "samples": combined,
        "train": train,
        "val": val,
        "test": test,
    }
    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} task=myopia total={len(combined)} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )
    return manifest


def build_multidisease_manifest(
    dataset_root: Path,
    output_path: Path,
    *,
    extra_root: Path | None = None,
    sources: tuple[str, ...] = ("rfmid", "odir"),
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    """다질환 Phase 4 — RFMiD 46질환 + ODIR 8질환 멀티레이블."""
    data_root = dataset_root.expanduser().resolve()
    extra = extra_root.expanduser().resolve() if extra_root else None
    manifest_root = _resolve_manifest_root(data_root, extra)
    all_samples: list[dict] = []
    counts: dict[str, int] = {}

    for name in sources:
        loader = MULTIDISEASE_LOADERS.get(name)
        if loader is None:
            raise ValueError(f"unknown multidisease source={name!r}; choose from {sorted(MULTIDISEASE_LOADERS)}")
        src_root = extra if extra is not None else data_root
        loaded = loader(src_root, manifest_root=manifest_root)  # type: ignore[operator]
        counts[name] = len(loaded)
        all_samples.extend(loaded)

    train, val, test = split_samples(
        all_samples,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )
    for chunk, split_name in ((train, "train"), (val, "val"), (test, "test")):
        for sample in chunk:
            sample["split"] = split_name
    combined = train + val + test
    manifest = {
        "data_dir": str(manifest_root),
        "task": "multidisease",
        "sources": counts,
        "total": len(combined),
        "key_diseases": [
            "dr",
            "amd",
            "glaucoma",
            "cataract",
            "myopia",
            "brvo",
            "mh",
            "htn",
        ],
        "samples": combined,
        "train": train,
        "val": val,
        "test": test,
    }
    out = output_path if output_path.is_absolute() else Path.cwd() / output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"OK {out} task=multidisease total={len(combined)} "
        f"train={len(train)} val={len(val)} test={len(test)} sources={counts}"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build multi-indication manifest")
    parser.add_argument("--data-root", type=Path, required=True, help="~/workspace/dataset/Glaucoma_raw")
    parser.add_argument(
        "--extra-root",
        type=Path,
        default=None,
        help="추가 Glaucoma 데이터 (예: /dataset/Glaucoma_extra)",
    )
    parser.add_argument(
        "--task",
        choices=("multi", "glaucoma", "amd", "myopia", "multidisease"),
        default="multi",
        help="glaucoma | amd | myopia | multidisease | multi",
    )
    parser.add_argument(
        "--sources",
        default="refuge,brazil,adam,odir",
        help="multi: refuge,brazil,... · glaucoma: g1020,refuge,origa,airogs,rimone",
    )
    parser.add_argument("--output", type=Path, default=Path("training/manifests/multi_indication.json"))
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()

    if args.task == "amd":
        build_amd_manifest(
            data_root,
            args.output,
            extra_root=args.extra_root,
            sources=tuple(s.strip() for s in args.sources.split(",") if s.strip())
            or ("amdnet23", "odir_amd", "rfmid_amd"),
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        return

    if args.task == "myopia":
        build_myopia_manifest(
            data_root,
            args.output,
            extra_root=args.extra_root,
            sources=tuple(s.strip() for s in args.sources.split(",") if s.strip()) or ("palm",),
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        return

    if args.task == "multidisease":
        build_multidisease_manifest(
            data_root,
            args.output,
            extra_root=args.extra_root,
            sources=tuple(s.strip() for s in args.sources.split(",") if s.strip()) or ("rfmid", "odir"),
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        return

    if args.task == "glaucoma":
        src = tuple(
            s.strip()
            for s in args.sources.replace(",", " ").split()
            if s.strip()
        )
        build_glaucoma_manifest(
            data_root,
            args.output,
            extra_root=args.extra_root,
            sources=src or None,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
            version=2 if args.extra_root else 1,
            unified_split=True if args.extra_root else None,
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
