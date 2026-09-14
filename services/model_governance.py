"""Model governance registry — MEDI remains model SSOT; no artifact duplication."""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "models" / "model_registry.json"
DEFAULT_ONNX = Path(__file__).resolve().parents[1] / "models" / "retinal_v10.onnx"

# Known hash captured 2026-09-14 for retinal_v10.onnx (local engineering artifact)
KNOWN_RETINAL_V10_SHA256 = "a5d3467e2d27ccf2e7bc9bdf42f611ba7ab4d8f221ddcf8921742c38b4ef6ecc"


def sha256_file(path: Path, *, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    if REGISTRY_PATH.is_file():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"models": {}, "schema_version": "model-registry.v1"}


def resolve_v10_path() -> Path:
    env = os.getenv("MEDI_V10_MODEL_PATH")
    if env:
        return Path(env)
    return DEFAULT_ONNX


def get_model_governance(
    *,
    model_id: str = "retinal_v10",
    preprocess_version: str = "retinal-preproc-v1",
    qc_version: str = "qc-v1.0-provisional",
    contract_version: str = "mvp02.v1",
    build_version: str | None = None,
) -> dict[str, Any]:
    """Return governance block for inference results / traceability."""
    reg = load_registry()
    entry = (reg.get("models") or {}).get(model_id) or {}
    path = resolve_v10_path()
    artifact_hash = entry.get("artifact_sha256") or KNOWN_RETINAL_V10_SHA256
    hash_verified = None
    if path.is_file():
        try:
            live = sha256_file(path)
            hash_verified = live == artifact_hash
            artifact_hash = live
        except OSError:
            hash_verified = False

    return {
        "model_id": model_id,
        "model_version": entry.get("model_version") or "v10c",
        "model_artifact": entry.get("artifact") or "models/retinal_v10.onnx",
        "model_artifact_hash": artifact_hash,
        "model_hash_verified": hash_verified,
        "architecture": entry.get("architecture") or "efficientnet_b4",
        "preprocessing_version": preprocess_version,
        "qc_version": qc_version,
        "contract_version": contract_version,
        "deployment_build_version": build_version
        or os.getenv("MEDI_BUILD_VERSION")
        or os.getenv("GIT_COMMIT")
        or "dev",
        "registry_schema": reg.get("schema_version") or "model-registry.v1",
    }
