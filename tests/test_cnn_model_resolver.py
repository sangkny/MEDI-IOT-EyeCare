"""CNN 모델 경로 resolver 단위 테스트."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.cnn_model_resolver import resolve_cnn_model


def test_explicit_path_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "retinal_v9.onnx").write_bytes(b"x")
    monkeypatch.delenv("MEDI_CNN_MODEL_PATH", raising=False)
    monkeypatch.delenv("MEDI_CNN_MODEL_VERSION", raising=False)
    r = resolve_cnn_model(
        app_root=tmp_path,
        explicit_path="models/retinal_v9.onnx",
    )
    assert r.source == "explicit"
    assert r.relative_path == "models/retinal_v9.onnx"


def test_version_v3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "retinal_v3.onnx").write_bytes(b"x")
    monkeypatch.delenv("MEDI_CNN_MODEL_PATH", raising=False)
    r = resolve_cnn_model(app_root=tmp_path, version="v3")
    assert r.version == "v3"
    assert r.source == "version"
    assert r.absolute_path.name == "retinal_v3.onnx"


def test_auto_prefers_v3_over_v2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "retinal_v2.onnx").write_bytes(b"x")
    (models / "retinal_v3.onnx").write_bytes(b"x")
    monkeypatch.delenv("MEDI_CNN_MODEL_PATH", raising=False)
    r = resolve_cnn_model(app_root=tmp_path, version="auto")
    assert r.version == "v3"
    assert r.source == "auto"


def test_auto_falls_back_to_v2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "retinal_v2.onnx").write_bytes(b"x")
    monkeypatch.delenv("MEDI_CNN_MODEL_PATH", raising=False)
    r = resolve_cnn_model(app_root=tmp_path, version="auto")
    assert r.version == "v2"
