"""
파일명: test_iot_gateway.py
목적: iot gateway.py 단위·통합 테스트
히스토리:
  2026-06-11 - 현재 상태 문서화 + 히스토리 추가


IoT Gateway 단위 테스트 (D R4-IoT W1, Mock 0).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from services.iot_gateway import IoTGatewayService


@pytest.fixture
def gw() -> IoTGatewayService:
    return IoTGatewayService()


@pytest.mark.asyncio
async def test_register_and_ingest(gw: IoTGatewayService) -> None:
    dev = await gw.register_device(
        patient_id="P000001",
        device_type="tonometer",
    )
    m = await gw.ingest_measurement(
        patient_id="P000001",
        device_id=dev.device_id,
        device_type="tonometer",
        payload={"iop_mmhg": 18.0},
    )
    assert m.ontology_passed is True
    assert m.alerts == []


@pytest.mark.asyncio
async def test_high_iop_requires_alert(gw: IoTGatewayService) -> None:
    dev = await gw.register_device(patient_id="P000002", device_type="tonometer")
    m = await gw.ingest_measurement(
        patient_id="P000002",
        device_id=dev.device_id,
        device_type="tonometer",
        payload={"iop_mmhg": 24.0},
    )
    assert "high_iop_alert" in m.alerts
    assert m.ontology_passed is False


@pytest.mark.asyncio
async def test_hyperglycemia_alert(gw: IoTGatewayService) -> None:
    dev = await gw.register_device(patient_id="P000003", device_type="cgm")
    m = await gw.ingest_measurement(
        patient_id="P000003",
        device_id=dev.device_id,
        device_type="cgm",
        payload={"blood_glucose_mg_dl": 220, "hyperglycemia_alert": True},
    )
    assert m.ontology_passed is True
    assert "hyperglycemia_alert" in m.alerts


@pytest.mark.asyncio
async def test_get_latest(gw: IoTGatewayService) -> None:
    dev = await gw.register_device(patient_id="P000004", device_type="bp_monitor")
    await gw.ingest_measurement(
        patient_id="P000004",
        device_id=dev.device_id,
        device_type="bp_monitor",
        payload={"bp_systolic": 120, "bp_diastolic": 80},
    )
    rows = await gw.get_latest("P000004")
    assert len(rows) == 1
