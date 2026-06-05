"""pytest 마커 정책 — GHA(unit) vs 로컬(integration).

GHA CI:  ``pytest -m unit`` (DB/Redis/uvicorn/ONNX/LLM 불필요)
로컬:    ``scripts/local-test.sh`` 또는 ``pytest -m integration``
"""
from __future__ import annotations

import pytest

# ── 파일 단위 기본 마커 (모듈명, tests.test_* ) ───────────────
_UNIT_MODULES = frozenset({
    "test_cdr_estimator",
    "test_comprehensive_fundus",
    "test_fundus_formats",
    "test_fundus_video",
    "test_glaucoma_cnn",
    "test_glaucoma_critic",
    "test_glaucoma_gradcam",
    "test_image_storage",
    "test_integrated_diagnosis",
    "test_iot_gateway",
    "test_messidor_manifest",
    "test_real_image",
    "test_retinal_preprocess",
    "test_vision_router",
})

_INTEGRATION_DB_MODULES = frozenset({
    "test_auth",
    "test_auto_promote",
    "test_billing",
    "test_clinical",
    "test_dashboard_api",
    "test_fhir_export",
    "test_images",
    "test_messidor_import",
    "test_patient_history",
})

_REQUIRES_LLM_MODULES = frozenset({
    "test_e2e_context",
    "test_e2e_week4_full_flow",
    "test_knowledge_base",
})

_REQUIRES_ONNX_MODULES = frozenset({
    "test_inference_router",
    "test_retinal_cnn",
})

# 클래스 단위 (혼합 파일)
_UNIT_CLASSES = frozenset({
    "TestEyeAnalyzerUnit",
    "TestReportGenUnit",
})

_INTEGRATION_DB_CLASSES = frozenset({
    "TestHealthAPI",
    "TestPatientAPI",
    "TestDiagnosisAPI",
    "TestDashboardAPI",
    "TestPgvector",
    "TestImageUploadAPI",
    "TestPatientHistoryAPI",
    "TestPatientTrendAPI",
    "TestPatientReportsAPI",
    "TestCacheService",
})

_REQUIRES_LLM_CLASSES = frozenset({
    "TestAIDiagnosis",
    "TestImageAnalysis",
    "TestEyeAnalyzerFundus",
    "TestEyeAnalyzerOCT",
    "TestEyeAnalyzerGlaucoma",
    "TestOntologyIntegration",
    "TestReportGenDiabetic",
    "TestReportGenGlaucoma",
    "TestEyeAnalyzerToReport",
    "TestKnowledgeBaseLoad",
    "TestKnowledgeBaseSearch",
    "TestRAGContext",
    "TestWeek4DiabeticFullFlow",
})


def _add_marker(item: pytest.Item, marker: str) -> None:
    if marker not in {m.name for m in item.iter_markers()}:
        item.add_marker(getattr(pytest.mark, marker))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """파일·클래스 규칙으로 마커 자동 부여 (파일 상단 pytestmark 와 동기)."""
    for item in items:
        mod = item.module.__name__.split(".")[-1] if item.module else ""
        cls = getattr(item.cls, "__name__", None) if item.cls else None

        if mod in _REQUIRES_ONNX_MODULES:
            _add_marker(item, "requires_onnx")
            _add_marker(item, "integration")
            continue

        if mod in _REQUIRES_LLM_MODULES:
            _add_marker(item, "requires_llm")
            _add_marker(item, "integration")
            if mod == "test_knowledge_base.py":
                _add_marker(item, "requires_db")
            continue

        if cls in _REQUIRES_LLM_CLASSES:
            _add_marker(item, "requires_llm")
            _add_marker(item, "integration")
            if cls in {"TestImageAnalysis", "TestPgvector", "TestImageUploadAPI"}:
                _add_marker(item, "requires_db")
            continue

        if cls in _UNIT_CLASSES:
            _add_marker(item, "unit")
            continue

        if cls in _INTEGRATION_DB_CLASSES:
            _add_marker(item, "integration")
            _add_marker(item, "requires_db")
            continue

        if mod in _UNIT_MODULES:
            _add_marker(item, "unit")
            continue

        if mod in _INTEGRATION_DB_MODULES:
            _add_marker(item, "integration")
            _add_marker(item, "requires_db")
            continue

        if mod == "test_e2e" and cls is None:
            _add_marker(item, "integration")
            _add_marker(item, "requires_db")
