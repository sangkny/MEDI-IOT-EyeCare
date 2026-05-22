"""CNN ONNX/PT 경로 해석 — 버전 선택(v1/v2/v3/auto) 및 명시 경로 우선.

환경 변수 (우선순위):
  1. ``MEDI_CNN_MODEL_PATH`` — 비어 있지 않으면 그대로 사용
  2. ``MEDI_CNN_MODEL_VERSION`` — ``v1`` | ``v2`` | ``v3`` | ``auto`` (기본 ``auto``)
  3. ``auto`` — 로컬 ``models/retinal_v3.onnx`` → v2 → v1 순 탐색

``MEDI_CNN_AUTO_PULL=1`` 이면 ``scripts/sync_cnn_model.py`` 가 기동 시 MinIO에서 내려받는다.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

VERSION_ORDER = ("v3", "v2", "v1")
_VERSION_RE = re.compile(r"^retinal_(v\d+)\.(onnx|pt)$", re.I)


@dataclass(frozen=True)
class ResolvedCnnModel:
    relative_path: str
    absolute_path: Path
    version: str | None
    arch: str | None
    source: str  # explicit | version | auto


def get_app_root() -> Path:
    raw = (os.getenv("MEDI_APP_ROOT") or "/app").strip()
    return Path(raw)


def _model_filename(version: str, ext: str = "onnx") -> str:
    v = version.lower().removeprefix("v")
    return f"retinal_v{v}.{ext}"


def list_local_retinal_versions(models_dir: Path) -> list[str]:
    found: list[tuple[int, str]] = []
    if not models_dir.is_dir():
        return []
    for p in models_dir.glob("retinal_v*.onnx"):
        m = _VERSION_RE.match(p.name)
        if m:
            found.append((int(m.group(1)[1:]), m.group(1).lower()))
    found.sort(key=lambda x: x[0], reverse=True)
    return [v for _, v in found]


def _read_arch_from_meta(meta_path: Path) -> str | None:
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        arch = data.get("arch")
        return str(arch) if arch else None
    except (json.JSONDecodeError, OSError):
        return None


def resolve_cnn_model(
    *,
    app_root: Path | None = None,
    explicit_path: str | None = None,
    version: str | None = None,
) -> ResolvedCnnModel:
    """로컬 파일 기준으로 CNN 모델 경로를 결정한다."""
    root = app_root or get_app_root()
    models_dir = root / "models"

    raw_explicit = (explicit_path if explicit_path is not None else os.getenv("MEDI_CNN_MODEL_PATH") or "").strip()
    if raw_explicit:
        rel = raw_explicit.replace("\\", "/")
        abs_path = Path(rel) if Path(rel).is_absolute() else root / rel
        ver = _version_from_filename(abs_path.name)
        meta = abs_path.with_suffix(".meta.json")
        return ResolvedCnnModel(
            relative_path=rel,
            absolute_path=abs_path,
            version=ver,
            arch=_read_arch_from_meta(meta),
            source="explicit",
        )

    ver_env = (version if version is not None else os.getenv("MEDI_CNN_MODEL_VERSION") or "auto").strip().lower()
    if ver_env in VERSION_ORDER:
        rel = f"models/{_model_filename(ver_env)}"
        abs_path = root / rel
        meta = abs_path.with_suffix(".meta.json")
        return ResolvedCnnModel(
            relative_path=rel,
            absolute_path=abs_path,
            version=ver_env,
            arch=_read_arch_from_meta(meta),
            source="version",
        )

    if ver_env != "auto":
        ver_env = "auto"

    local_versions = list_local_retinal_versions(models_dir)
    for v in VERSION_ORDER:
        if v in local_versions:
            rel = f"models/{_model_filename(v)}"
            abs_path = root / rel
            meta = abs_path.with_suffix(".meta.json")
            return ResolvedCnnModel(
                relative_path=rel,
                absolute_path=abs_path,
                version=v,
                arch=_read_arch_from_meta(meta),
                source="auto",
            )

    fallback = "v2"
    rel = f"models/{_model_filename(fallback)}"
    abs_path = root / rel
    return ResolvedCnnModel(
        relative_path=rel,
        absolute_path=abs_path,
        version=fallback,
        arch=None,
        source="auto",
    )


def _version_from_filename(name: str) -> str | None:
    m = _VERSION_RE.match(name)
    return m.group(1).lower() if m else None


def versions_to_sync(version: str | None = None) -> list[str]:
    """MinIO pull 시도 순서."""
    v = (version or os.getenv("MEDI_CNN_MODEL_VERSION") or "auto").strip().lower()
    if v in VERSION_ORDER:
        return [v]
    return list(VERSION_ORDER)
