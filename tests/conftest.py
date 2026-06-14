"""
파일명: conftest.py
목적: pytest 마커 자동 부여 — unit/integration/slow/requires_llm + LLM mock
히스토리:
  2026-06-12 - unit/smoke LLM mock 강화, .env.test 로드, mock_llm_client fixture
  2026-06-11 - test_diagnosis_pipeline* unit 마커 + medi-regression.sh 연동
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가

GHA CI: ``pytest -m unit`` (DB/Redis/uvicorn/ONNX/LLM 불필요)
로컬: ``scripts/medi-regression.sh {unit|smoke|slow|full}``
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

# ── .env.test 로드 (pytest 시작 시 1회) ───────────────────────
def _load_env_test() -> None:
    root = Path(__file__).resolve().parents[1]
    env_file = root / ".env.test"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env_test()


class MockLLMClient:
    """unit/smoke — LM Studio 연결 없이 결정론적 응답."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def chat(
        self,
        prompt: str,
        role: Any = None,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Any:
        from llm.base import LLMProvider, LLMResponse, ModelRole

        resolved = role if role is not None else ModelRole.FAST
        return LLMResponse(
            content="테스트 응답",
            model_used="mock/test",
            provider=LLMProvider.LOCAL,
            role=resolved,
            input_tokens=1,
            output_tokens=2,
        )

    async def chat_messages(
        self,
        messages: list[dict[str, str]],
        role: Any = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Any:
        return await self.chat("", role=role, max_tokens=max_tokens, temperature=temperature)

    async def embed(self, text: str) -> Any:
        from llm.base import EmbedResponse, LLMProvider

        return EmbedResponse(
            vector=[0.0] * 8,
            model_used="mock/embed",
            provider=LLMProvider.LOCAL,
        )

    def health_check_all(self) -> dict[str, Any]:
        return {"main": {"status": "mock"}, "embed": {"status": "mock"}}


def _needs_real_llm(item: pytest.Item | pytest.Function) -> bool:
    names = {m.name for m in item.iter_markers()}
    return bool(names & {"slow", "requires_llm", "requires_lm_studio"})


@pytest.fixture
def mock_llm_client(monkeypatch: pytest.MonkeyPatch) -> MockLLMClient:
    """명시적 LLM mock — 항상 ``테스트 응답`` 반환."""
    client = MockLLMClient()
    try:
        import llm.client as llm_client_mod

        monkeypatch.setattr(llm_client_mod, "LLMClient", lambda *a, **k: client)
    except ImportError:
        pass
    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    monkeypatch.setenv("PYTEST_LLM_MOCK", "1")
    return client


@pytest.fixture(autouse=True)
def _unit_llm_mock_policy(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """unit/smoke: LLM mock · slow/requires_llm: 실 LM Studio (e4b, .env.test)."""
    if _needs_real_llm(request.node):
        monkeypatch.delenv("AGENT_FOUR_AGENT_MOCK", raising=False)
        monkeypatch.delenv("PYTEST_LLM_MOCK", raising=False)
        return

    monkeypatch.setenv("AGENT_FOUR_AGENT_MOCK", "1")
    monkeypatch.setenv("PYTEST_LLM_MOCK", "1")
    monkeypatch.setenv(
        "LOCAL_HEAVY_MODEL",
        os.getenv("LOCAL_HEAVY_MODEL", "google/gemma-4-e4b"),
    )
    monkeypatch.setenv(
        "LOCAL_FAST_MODEL",
        os.getenv("LOCAL_FAST_MODEL", "google/gemma-4-e4b"),
    )
    try:
        import llm.client as llm_client_mod

        monkeypatch.setattr(llm_client_mod, "LLMClient", MockLLMClient)
    except ImportError:
        pass

# ── 파일 단위 기본 마커 (모듈명, tests.test_* ) ───────────────
_UNIT_MODULES = frozenset({
    "test_cdr_estimator",
    "test_comprehensive_fundus",
    "test_comprehensive_modes",
    "test_fundus_formats",
    "test_fundus_enhancement",
    "test_gl_extra2_manifest",
    "test_fundus_video",
    "test_glaucoma_cnn",
    "test_gl_ensemble",
    "test_glaucoma_critic",
    "test_glaucoma_gradcam",
    "test_image_storage",
    "test_integrated_diagnosis",
    "test_iot_gateway",
    "test_messidor_manifest",
    "test_amd_manifest",
    "test_glaucoma_manifest",
    "test_glaucoma_train",
    "test_multitask_model",
    "test_amd_cnn",
    "test_multidisease_cnn",
    "test_multidisease_schema",
    "test_v10_model",
    "test_v10_export",
    "test_real_image",
    "test_retinal_preprocess",
    "test_vision_router",
    "test_diagnosis_pipeline",
    "test_diagnosis_pipeline_four_agent",
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


def _lm_studio_ready() -> bool:
    """LM Studio ``/v1/models`` 200 + 비어있지 않은 data[] (CI skip 가드)."""
    try:
        import httpx

        base = os.getenv("LLM_BASE_URL", "http://host.docker.internal:1234/v1")
        r = httpx.get(f"{base}/models", timeout=2.0)
        if r.status_code != 200:
            return False
        return bool((r.json() or {}).get("data"))
    except Exception:
        return False


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

    if not _lm_studio_ready():
        skip_lm = pytest.mark.skip(
            reason="LM Studio 미가동 — requires_lm_studio (VISION 분석 테스트)"
        )
        for item in items:
            if "requires_lm_studio" in {m.name for m in item.iter_markers()}:
                item.add_marker(skip_lm)
