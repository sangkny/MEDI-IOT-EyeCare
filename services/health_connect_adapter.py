"""
Google Health Connect 어댑터 — Android 레코드 → MEDI-IOT 표준 · FHIR Bundle (D R4-IoT W2).
"""
from __future__ import annotations

from typing import Any

from services.health_sync import normalize_health_connect_records


class HealthConnectAdapter:
    """Health Connect API 호환 레코드 파싱."""

    def parse_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """원본 레코드 → HealthSyncService records 형식 (타입·값 정규화)."""
        out: list[dict[str, Any]] = []
        for r in records:
            rec_type = r.get("record_type") or r.get("type")
            if not rec_type and r.get("blood_glucose") is not None:
                rec_type = "BloodGlucoseRecord"
                r = {**r, "record_type": rec_type, "value": r["blood_glucose"]}
            if not rec_type and r.get("heart_rate") is not None:
                rec_type = "HeartRateRecord"
                r = {**r, "record_type": rec_type, "value": r["heart_rate"]}
            if rec_type:
                out.append(
                    {
                        "record_type": rec_type,
                        "value": r.get("value"),
                        "unit": r.get("unit", ""),
                        "time": r.get("time") or r.get("timestamp"),
                        "data_origin": r.get("data_origin", ""),
                    }
                )
        return out

    def to_fhir_bundle(self, records: list[dict[str, Any]], patient_id: str = "") -> dict[str, Any]:
        normalized = normalize_health_connect_records(self.parse_records(records))
        entries = []
        for s in normalized:
            entries.append(
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": {"text": s.sample_type},
                        "subject": {"reference": f"Patient/{patient_id}"} if patient_id else {},
                        "effectiveDateTime": s.recorded_at,
                        "valueQuantity": {"value": s.value, "unit": s.unit},
                    }
                }
            )
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries,
        }
