"""IoT Gateway API (D R4-IoT W1)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from services.health_connect_adapter import HealthConnectAdapter
from services.healthkit_adapter import HealthKitAdapter
from services.health_sync import get_health_sync
from services.iot_gateway import get_iot_gateway

log = logging.getLogger("api.iot")
router = APIRouter()
_healthkit = HealthKitAdapter()
_health_connect = HealthConnectAdapter()


class DeviceRegisterRequest(BaseModel):
    patient_id: str
    device_type: str = Field(..., description="tonometer|oct|perimeter|wearable|cgm|bp_monitor")
    label: str = ""
    device_id: str | None = None


class DeviceRegisterResponse(BaseModel):
    device_id: str
    patient_id: str
    device_type: str
    label: str
    registered_at: str


class MeasurementIngestRequest(BaseModel):
    patient_id: str
    device_id: str
    device_type: str
    recorded_at: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class MeasurementResponse(BaseModel):
    measurement_id: str
    patient_id: str
    device_id: str
    device_type: str
    recorded_at: str
    payload: dict[str, Any]
    ontology_passed: bool
    alerts: list[str]


@router.post(
    "/devices/register",
    response_model=DeviceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_device(body: DeviceRegisterRequest) -> DeviceRegisterResponse:
    gw = get_iot_gateway()
    try:
        dev = await gw.register_device(
            patient_id=body.patient_id,
            device_type=body.device_type,
            label=body.label,
            device_id=body.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return DeviceRegisterResponse(
        device_id=dev.device_id,
        patient_id=dev.patient_id,
        device_type=dev.device_type,
        label=dev.label,
        registered_at=dev.registered_at,
    )


@router.post(
    "/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_measurement(body: MeasurementIngestRequest) -> MeasurementResponse:
    gw = get_iot_gateway()
    try:
        m = await gw.ingest_measurement(
            patient_id=body.patient_id,
            device_id=body.device_id,
            device_type=body.device_type,
            recorded_at=body.recorded_at,
            payload=body.payload,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return MeasurementResponse(
        measurement_id=m.measurement_id,
        patient_id=m.patient_id,
        device_id=m.device_id,
        device_type=m.device_type,
        recorded_at=m.recorded_at,
        payload=m.payload,
        ontology_passed=m.ontology_passed,
        alerts=m.alerts,
    )


class HealthKitIngestBody(BaseModel):
    patient_id: str
    device_id: str = "healthkit-mobile"
    blood_glucose: float | None = None
    heart_rate: float | None = None
    systolic: float | None = None
    diastolic: float | None = None
    unit: str = "mg/dL"
    timestamp: str | None = None


class HealthConnectIngestBody(BaseModel):
    patient_id: str
    device_id: str = "health-connect-mobile"
    records: list[dict[str, Any]] = Field(default_factory=list)
    blood_glucose: float | None = None
    heart_rate: float | None = None
    unit: str = ""
    timestamp: str | None = None


@router.post("/healthkit", response_model=MeasurementResponse, status_code=status.HTTP_201_CREATED)
async def ingest_healthkit(body: HealthKitIngestBody) -> MeasurementResponse:
    """Apple HealthKit 단순 JSON 수신 (W2)."""
    payload = body.model_dump()
    samples = _healthkit.to_healthkit_samples(payload)
    if not samples and body.blood_glucose is not None:
        g = _healthkit.parse_blood_glucose(payload)
        samples = [
            {
                "type": "HKQuantityTypeIdentifierBloodGlucose",
                "value": g.value,
                "unit": g.unit,
                "start_date": g.timestamp,
            }
        ]
    if not samples:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no healthkit fields")
    svc = get_health_sync()
    try:
        m = await svc.sync_healthkit(
            patient_id=body.patient_id,
            device_id=body.device_id,
            samples=samples,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MeasurementResponse(
        measurement_id=m.measurement_id,
        patient_id=m.patient_id,
        device_id=m.device_id,
        device_type=m.device_type,
        recorded_at=m.recorded_at,
        payload=m.payload,
        ontology_passed=m.ontology_passed,
        alerts=m.alerts,
    )


@router.post(
    "/health-connect",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_health_connect(body: HealthConnectIngestBody) -> MeasurementResponse:
    """Android Health Connect 레코드 수신 (W2)."""
    records = list(body.records)
    if body.blood_glucose is not None:
        records.append(
            {
                "record_type": "BloodGlucoseRecord",
                "value": body.blood_glucose,
                "unit": body.unit or "mg/dL",
                "time": body.timestamp,
            }
        )
    if body.heart_rate is not None:
        records.append(
            {
                "record_type": "HeartRateRecord",
                "value": body.heart_rate,
                "unit": "count/min",
                "time": body.timestamp,
            }
        )
    parsed = _health_connect.parse_records(records)
    if not parsed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no health connect records")
    svc = get_health_sync()
    try:
        m = await svc.sync_health_connect(
            patient_id=body.patient_id,
            device_id=body.device_id,
            records=parsed,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MeasurementResponse(
        measurement_id=m.measurement_id,
        patient_id=m.patient_id,
        device_id=m.device_id,
        device_type=m.device_type,
        recorded_at=m.recorded_at,
        payload=m.payload,
        ontology_passed=m.ontology_passed,
        alerts=m.alerts,
    )


@router.get("/latest/{patient_id}", response_model=list[MeasurementResponse])
async def get_latest_iot_alias(patient_id: str, limit: int = 20) -> list[MeasurementResponse]:
    """최신 IoT 측정 조회 (별칭 — /patients/{id}/latest 와 동일)."""
    return await get_latest_measurements(patient_id, limit=limit)


@router.get("/patients/{patient_id}/latest", response_model=list[MeasurementResponse])
async def get_latest_measurements(
    patient_id: str,
    limit: int = 20,
) -> list[MeasurementResponse]:
    gw = get_iot_gateway()
    rows = await gw.get_latest(patient_id, limit=limit)
    return [
        MeasurementResponse(
            measurement_id=m.measurement_id,
            patient_id=m.patient_id,
            device_id=m.device_id,
            device_type=m.device_type,
            recorded_at=m.recorded_at,
            payload=m.payload,
            ontology_passed=m.ontology_passed,
            alerts=m.alerts,
        )
        for m in rows
    ]


@router.websocket("/stream/{patient_id}")
async def iot_stream(websocket: WebSocket, patient_id: str) -> None:
    await websocket.accept()
    gw = get_iot_gateway()
    q = gw.subscribe(patient_id)
    try:
        await websocket.send_json({"type": "connected", "patient_id": patient_id})
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_json(msg)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        gw.unsubscribe(patient_id, q)
