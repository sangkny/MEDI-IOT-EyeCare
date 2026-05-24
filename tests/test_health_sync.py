"""HealthKit / Health Connect 정규화 (W2)."""
from __future__ import annotations

import pytest

from services.health_sync import (
    normalize_health_connect_records,
    normalize_healthkit_samples,
    samples_to_iot_payload,
)
from services.health_sync import HealthSyncService
from services.iot_gateway import IoTGatewayService


@pytest.mark.unit
def test_normalize_healthkit_heart_rate():
    samples = normalize_healthkit_samples(
        [
            {
                "type": "HKQuantityTypeIdentifierHeartRate",
                "value": 72.0,
                "unit": "count/min",
                "start_date": "2026-05-24T10:00:00Z",
            }
        ]
    )
    assert len(samples) == 1
    assert samples[0].sample_type == "heart_rate_bpm"
    assert samples[0].value == 72.0


@pytest.mark.unit
def test_normalize_health_connect_glucose():
    records = normalize_health_connect_records(
        [
            {
                "record_type": "BloodGlucoseRecord",
                "value": 110.0,
                "unit": "mg/dL",
                "time": "2026-05-24T11:00:00Z",
            }
        ]
    )
    assert records[0].sample_type == "blood_glucose_mg_dl"


@pytest.mark.unit
def test_samples_to_payload_merges():
    hk = normalize_healthkit_samples(
        [
            {
                "type": "HKQuantityTypeIdentifierHeartRate",
                "value": 80.0,
                "start_date": "2026-05-24T10:00:00Z",
            }
        ]
    )
    payload = samples_to_iot_payload(hk)
    assert payload["heart_rate_bpm"] == 80.0
    assert payload["sample_count"] == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_health_sync_ingest():
    gw = IoTGatewayService()
    dev = await gw.register_device(
        patient_id="p1", device_type="wearable", label="watch"
    )
    svc = HealthSyncService(gateway=gw)
    m = await svc.sync_healthkit(
        patient_id="p1",
        device_id=dev.device_id,
        samples=[
            {
                "type": "HKQuantityTypeIdentifierHeartRate",
                "value": 95.0,
                "start_date": "2026-05-24T12:00:00Z",
            }
        ],
    )
    assert m.measurement_id
    assert m.payload.get("heart_rate_bpm") == 95.0
