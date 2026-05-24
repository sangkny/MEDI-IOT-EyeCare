"""웨어러블 HealthKit / Health Connect 동기화 API (D R4-IoT W2)."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.health_sync import get_health_sync

log = logging.getLogger("api.wearable")
router = APIRouter()


class HealthKitSyncRequest(BaseModel):
    patient_id: str
    device_id: str
    samples: list[dict[str, Any]] = Field(
        default_factory=list,
        description="HealthKit quantity samples (type, value, unit, start_date)",
    )


class HealthConnectSyncRequest(BaseModel):
    patient_id: str
    device_id: str
    records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Health Connect records (record_type, value, unit, time)",
    )


class WearableSyncResponse(BaseModel):
    measurement_id: str
    patient_id: str
    ontology_passed: bool
    alerts: list[str]
    payload: dict[str, Any]


@router.post(
    "/healthkit/sync",
    response_model=WearableSyncResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apple HealthKit 샘플 배치 동기화",
)
async def sync_healthkit(body: HealthKitSyncRequest) -> WearableSyncResponse:
    svc = get_health_sync()
    try:
        m = await svc.sync_healthkit(
            patient_id=body.patient_id,
            device_id=body.device_id,
            samples=body.samples,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WearableSyncResponse(
        measurement_id=m.measurement_id,
        patient_id=m.patient_id,
        ontology_passed=m.ontology_passed,
        alerts=m.alerts,
        payload=m.payload,
    )


@router.post(
    "/health-connect/sync",
    response_model=WearableSyncResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Android Health Connect 레코드 동기화",
)
async def sync_health_connect(body: HealthConnectSyncRequest) -> WearableSyncResponse:
    svc = get_health_sync()
    try:
        m = await svc.sync_health_connect(
            patient_id=body.patient_id,
            device_id=body.device_id,
            records=body.records,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WearableSyncResponse(
        measurement_id=m.measurement_id,
        patient_id=m.patient_id,
        ontology_passed=m.ontology_passed,
        alerts=m.alerts,
        payload=m.payload,
    )
