"""HealthKit / Health Connect → IoT Gateway 정규화 (D R4-IoT W2).

모바일 앱이 플랫폼 SDK로 읽은 건강 데이터를 공통 JSON으로 POST 한다.
서버는 ontology 검증 후 IoTMeasurement 로 저장한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from services.iot_gateway import IoTGatewayService, IoTMeasurement, get_iot_gateway

log = logging.getLogger("services.health_sync")

HealthPlatform = Literal["healthkit", "health_connect"]

# HealthKit type → 내부 payload 키
HEALTHKIT_TYPE_MAP: dict[str, str] = {
    "HKQuantityTypeIdentifierHeartRate": "heart_rate_bpm",
    "HKQuantityTypeIdentifierOxygenSaturation": "spo2_pct",
    "HKQuantityTypeIdentifierBloodGlucose": "blood_glucose_mg_dl",
    "HKQuantityTypeIdentifierStepCount": "steps",
}

# Health Connect record type → 내부 payload 키
HEALTH_CONNECT_TYPE_MAP: dict[str, str] = {
    "HeartRateRecord": "heart_rate_bpm",
    "OxygenSaturationRecord": "spo2_pct",
    "BloodGlucoseRecord": "blood_glucose_mg_dl",
    "StepsRecord": "steps",
}


@dataclass(frozen=True)
class NormalizedHealthSample:
    platform: HealthPlatform
    sample_type: str
    value: float
    unit: str
    recorded_at: str
    source_name: str = ""


def normalize_healthkit_samples(samples: list[dict[str, Any]]) -> list[NormalizedHealthSample]:
    out: list[NormalizedHealthSample] = []
    for s in samples:
        hk_type = str(s.get("type") or s.get("quantity_type") or "")
        key = HEALTHKIT_TYPE_MAP.get(hk_type)
        if not key:
            continue
        val = s.get("value")
        if val is None:
            continue
        out.append(
            NormalizedHealthSample(
                platform="healthkit",
                sample_type=key,
                value=float(val),
                unit=str(s.get("unit") or ""),
                recorded_at=str(s.get("start_date") or s.get("recorded_at") or _now_iso()),
                source_name=str(s.get("source_name") or ""),
            )
        )
    return out


def normalize_health_connect_records(records: list[dict[str, Any]]) -> list[NormalizedHealthSample]:
    out: list[NormalizedHealthSample] = []
    for r in records:
        rec_type = str(r.get("record_type") or r.get("type") or "")
        key = HEALTH_CONNECT_TYPE_MAP.get(rec_type)
        if not key:
            continue
        val = r.get("value")
        if val is None:
            continue
        out.append(
            NormalizedHealthSample(
                platform="health_connect",
                sample_type=key,
                value=float(val),
                unit=str(r.get("unit") or ""),
                recorded_at=str(r.get("time") or r.get("recorded_at") or _now_iso()),
                source_name=str(r.get("data_origin") or ""),
            )
        )
    return out


def samples_to_iot_payload(samples: list[NormalizedHealthSample]) -> dict[str, Any]:
    """여러 샘플을 단일 측정 payload 로 병합 (최신 값 우선)."""
    payload: dict[str, Any] = {"source": "wearable_sync"}
    for s in samples:
        payload[s.sample_type] = s.value
        if s.platform == "healthkit":
            payload["healthkit_source"] = s.source_name or payload.get("healthkit_source", "")
        else:
            payload["health_connect_source"] = s.source_name or payload.get(
                "health_connect_source", ""
            )
    payload["sample_count"] = len(samples)
    return payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HealthSyncService:
    """HealthKit / Health Connect 배치 동기화."""

    def __init__(self, gateway: IoTGatewayService | None = None) -> None:
        self._gw = gateway or get_iot_gateway()

    async def sync_healthkit(
        self,
        *,
        patient_id: str,
        device_id: str,
        samples: list[dict[str, Any]],
    ) -> IoTMeasurement:
        normalized = normalize_healthkit_samples(samples)
        return await self._ingest(patient_id=patient_id, device_id=device_id, normalized=normalized)

    async def sync_health_connect(
        self,
        *,
        patient_id: str,
        device_id: str,
        records: list[dict[str, Any]],
    ) -> IoTMeasurement:
        normalized = normalize_health_connect_records(records)
        return await self._ingest(patient_id=patient_id, device_id=device_id, normalized=normalized)

    async def _ingest(
        self,
        *,
        patient_id: str,
        device_id: str,
        normalized: list[NormalizedHealthSample],
    ) -> IoTMeasurement:
        if not normalized:
            raise ValueError("no recognized health samples")
        payload = samples_to_iot_payload(normalized)
        recorded_at = normalized[0].recorded_at
        return await self._gw.ingest_measurement(
            patient_id=patient_id,
            device_id=device_id,
            device_type="wearable",
            payload=payload,
            recorded_at=recorded_at,
        )


_health_sync: HealthSyncService | None = None


def get_health_sync() -> HealthSyncService:
    global _health_sync
    if _health_sync is None:
        _health_sync = HealthSyncService()
    return _health_sync
