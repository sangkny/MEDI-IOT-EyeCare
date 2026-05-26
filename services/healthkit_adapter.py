"""
Apple HealthKit 어댑터 — IoT 표준 형식 · FHIR Observation 변환 (D R4-IoT W2).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class GlucoseReading:
    value: float
    unit: str
    timestamp: str
    patient_id: str = ""


@dataclass(frozen=True)
class BPReading:
    systolic: float
    diastolic: float
    unit: str
    timestamp: str
    patient_id: str = ""


@dataclass(frozen=True)
class HRReading:
    value: float
    unit: str
    timestamp: str
    patient_id: str = ""


class HealthKitAdapter:
    """HealthKit quantity sample → 내부 읽기 모델."""

    def parse_blood_glucose(self, data: dict[str, Any]) -> GlucoseReading:
        val = data.get("blood_glucose", data.get("value"))
        if val is None:
            raise ValueError("blood_glucose or value required")
        return GlucoseReading(
            value=float(val),
            unit=str(data.get("unit") or "mg/dL"),
            timestamp=str(data.get("timestamp") or data.get("start_date") or _now_iso()),
            patient_id=str(data.get("patient_id") or ""),
        )

    def parse_blood_pressure(self, data: dict[str, Any]) -> BPReading:
        sys_v = data.get("systolic", data.get("blood_pressure_systolic"))
        dia_v = data.get("diastolic", data.get("blood_pressure_diastolic"))
        if sys_v is None or dia_v is None:
            raise ValueError("systolic and diastolic required")
        return BPReading(
            systolic=float(sys_v),
            diastolic=float(dia_v),
            unit=str(data.get("unit") or "mmHg"),
            timestamp=str(data.get("timestamp") or data.get("start_date") or _now_iso()),
            patient_id=str(data.get("patient_id") or ""),
        )

    def parse_heart_rate(self, data: dict[str, Any]) -> HRReading:
        val = data.get("heart_rate", data.get("value"))
        if val is None:
            raise ValueError("heart_rate or value required")
        return HRReading(
            value=float(val),
            unit=str(data.get("unit") or "count/min"),
            timestamp=str(data.get("timestamp") or data.get("start_date") or _now_iso()),
            patient_id=str(data.get("patient_id") or ""),
        )

    def to_healthkit_samples(self, body: dict[str, Any]) -> list[dict[str, Any]]:
        """단순 JSON POST → HealthSyncService용 samples 리스트."""
        samples: list[dict[str, Any]] = []
        ts = body.get("timestamp")
        if body.get("blood_glucose") is not None:
            g = self.parse_blood_glucose(body)
            samples.append(
                {
                    "type": "HKQuantityTypeIdentifierBloodGlucose",
                    "value": g.value,
                    "unit": g.unit,
                    "start_date": g.timestamp,
                }
            )
        if body.get("heart_rate") is not None:
            h = self.parse_heart_rate(body)
            samples.append(
                {
                    "type": "HKQuantityTypeIdentifierHeartRate",
                    "value": h.value,
                    "unit": h.unit,
                    "start_date": h.timestamp,
                }
            )
        if body.get("systolic") is not None and body.get("diastolic") is not None:
            # HealthSync는 BP 키 미매핑 — payload 직접 병합용 확장 샘플
            bp = self.parse_blood_pressure(body)
            samples.append(
                {
                    "type": "HKQuantityTypeIdentifierBloodPressureSystolic",
                    "value": bp.systolic,
                    "unit": bp.unit,
                    "start_date": bp.timestamp,
                    "extra": {"diastolic": bp.diastolic},
                }
            )
        return samples

    def to_fhir_observation(self, reading: GlucoseReading | BPReading | HRReading) -> dict[str, Any]:
        if isinstance(reading, GlucoseReading):
            code = "15074-8"
            display = "Glucose [Moles/volume] in Blood"
            value = {"value": reading.value, "unit": reading.unit}
        elif isinstance(reading, BPReading):
            code = "85354-9"
            display = "Blood pressure panel"
            value = {
                "component": [
                    {"code": "8480-6", "value": reading.systolic, "unit": reading.unit},
                    {"code": "8462-4", "value": reading.diastolic, "unit": reading.unit},
                ]
            }
        else:
            code = "8867-4"
            display = "Heart rate"
            value = {"value": reading.value, "unit": reading.unit}

        return {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]},
            "effectiveDateTime": reading.timestamp,
            "valueQuantity": value,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
