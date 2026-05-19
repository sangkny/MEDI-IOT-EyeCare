"""IoT Gateway API (D R4-IoT W1)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from services.iot_gateway import get_iot_gateway

log = logging.getLogger("api.iot")
router = APIRouter()


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
