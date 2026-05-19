"""IoT Gateway — 기기 등록·측정 수집·실시간 스트림 (D R4-IoT W1)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ontology.base import Severity, ValidationError, ValidatorType
from ontology.validator import OntologyValidator

log = logging.getLogger("services.iot_gateway")

IOT_DEVICE_TYPES = frozenset(
    {"tonometer", "oct", "perimeter", "wearable", "cgm", "bp_monitor"}
)


@dataclass
class IoTDevice:
    device_id: str
    patient_id: str
    device_type: str
    label: str = ""
    registered_at: str = ""


@dataclass
class IoTMeasurement:
    measurement_id: str
    patient_id: str
    device_id: str
    device_type: str
    recorded_at: str
    payload: dict[str, Any]
    ontology_passed: bool
    alerts: list[str] = field(default_factory=list)


class IoTGatewayService:
    """인메모리 IoT 허브 (W1 — 추후 DB/MQTT 영속화)."""

    def __init__(self) -> None:
        self._devices: dict[str, IoTDevice] = {}
        self._measurements: dict[str, list[IoTMeasurement]] = defaultdict(list)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._validator = OntologyValidator.for_iot_device()

    async def register_device(
        self,
        *,
        patient_id: str,
        device_type: str,
        label: str = "",
        device_id: str | None = None,
    ) -> IoTDevice:
        if device_type not in IOT_DEVICE_TYPES:
            raise ValueError(f"invalid device_type: {device_type}")
        did = device_id or str(uuid.uuid4())
        dev = IoTDevice(
            device_id=did,
            patient_id=patient_id,
            device_type=device_type,
            label=label,
            registered_at=datetime.now(timezone.utc).isoformat(),
        )
        self._devices[did] = dev
        log.info("IoT device registered: %s type=%s", did[:8], device_type)
        return dev

    def _clinical_alerts(self, payload: dict[str, Any]) -> list[str]:
        alerts: list[str] = []
        iop = payload.get("iop_mmhg")
        if iop is not None:
            try:
                if float(iop) > 21:
                    alerts.append("high_iop_alert")
            except (TypeError, ValueError):
                pass
        glucose = payload.get("blood_glucose_mg_dl")
        if glucose is not None:
            try:
                if float(glucose) > 180:
                    alerts.append("hyperglycemia_alert")
            except (TypeError, ValueError):
                pass
        return alerts

    async def ingest_measurement(
        self,
        *,
        patient_id: str,
        device_id: str,
        device_type: str,
        recorded_at: str | None = None,
        payload: dict[str, Any],
    ) -> IoTMeasurement:
        if device_type not in IOT_DEVICE_TYPES:
            raise ValueError(f"invalid device_type: {device_type}")

        ts = recorded_at or datetime.now(timezone.utc).isoformat()
        data = {
            "patient_id": patient_id,
            "device_id": device_id,
            "device_type": device_type,
            "recorded_at": ts,
            **payload,
        }
        result = await self._validator.validate(data)
        alerts = self._clinical_alerts(payload)
        for code in alerts:
            if not payload.get(code):
                result.add(
                    ValidationError(
                        code="IOT-DEP-001",
                        message=f"{code} required when clinical threshold exceeded",
                        severity=Severity.ERROR,
                        validator=ValidatorType.DEPENDENCY,
                        field=code,
                    )
                )

        ont_ok = result.passed
        if alerts:
            payload = {**payload, **{a: True for a in alerts}}

        m = IoTMeasurement(
            measurement_id=str(uuid.uuid4()),
            patient_id=patient_id,
            device_id=device_id,
            device_type=device_type,
            recorded_at=ts,
            payload=payload,
            ontology_passed=ont_ok,
            alerts=alerts,
        )
        self._measurements[patient_id].append(m)
        await self._broadcast(patient_id, m)
        _emit_iot_metric("ingested", device_type)
        if alerts:
            _emit_iot_metric("alert", alerts[0])
        return m

    async def get_latest(
        self, patient_id: str, *, limit: int = 20
    ) -> list[IoTMeasurement]:
        rows = self._measurements.get(patient_id, [])
        return list(rows[-limit:])

    def subscribe(self, patient_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        self._subscribers[patient_id].append(q)
        return q

    def unsubscribe(self, patient_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(patient_id, [])
        if q in subs:
            subs.remove(q)

    async def _broadcast(self, patient_id: str, measurement: IoTMeasurement) -> None:
        msg = {
            "type": "measurement",
            "measurement_id": measurement.measurement_id,
            "patient_id": patient_id,
            "device_type": measurement.device_type,
            "payload": measurement.payload,
            "alerts": measurement.alerts,
            "ontology_passed": measurement.ontology_passed,
        }
        for q in list(self._subscribers.get(patient_id, [])):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass


_gateway: IoTGatewayService | None = None


def get_iot_gateway() -> IoTGatewayService:
    global _gateway
    if _gateway is None:
        _gateway = IoTGatewayService()
    return _gateway


def _emit_iot_metric(outcome: str, label: str = "") -> None:
    try:
        from prometheus_client import Counter

        global _IOT_COUNTER
        try:
            _IOT_COUNTER
        except NameError:
            _IOT_COUNTER = Counter(
                "medi_iot_measurements_total",
                "IoT 측정 수집",
                ["outcome", "device_type"],
            )
        _IOT_COUNTER.labels(outcome=outcome, device_type=label or "na").inc()
    except Exception:
        pass


__all__ = ["IoTGatewayService", "get_iot_gateway", "IoTDevice", "IoTMeasurement"]
