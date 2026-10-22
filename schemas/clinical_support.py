"""임상 지원 레코드의 요청·응답 스키마."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    study_kind: Literal["dataset", "prospective"] = "dataset"
    protocol_version: str | None = None
    description: str | None = None


class StudyRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    study_kind: str
    protocol_version: str | None
    status: str


class SiteCreate(BaseModel):
    study_id: str
    site_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)


class SubjectCreate(BaseModel):
    study_id: str
    site_id: str
    subject_code: str = Field(min_length=1, max_length=64)
    patient_id: str | None = None
    enrolled_on: date | None = None


class SubjectRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    site_id: str
    subject_code: str
    patient_id: str | None
    status: str


class VisitCreate(BaseModel):
    subject_id: str
    visit_code: str = Field(min_length=1, max_length=64)
    occurred_on: date
    repeat_no: int = Field(default=1, ge=1)
    window_id: str | None = None


class VisitRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject_id: str
    visit_code: str
    repeat_no: int
    occurred_on: date
    window_id: str | None


class QuestionnaireVersionCreate(BaseModel):
    definition_id: str
    version_number: int = Field(ge=1)
    items_json: str


class ObservationCreate(BaseModel):
    visit_id: str
    code: str = Field(min_length=1, max_length=64)
    laterality: Literal["OD", "OS", "OU", "NA"] = "NA"
    method: str = "NA"
    repeat_index: int = Field(default=1, ge=1)
    value_number: float | None = None
    value_text: str | None = None
    unit: str | None = None
    source: Literal["manual", "device", "import", "derived"] = "manual"
    recorded_by: str


class ObservationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    visit_id: str
    code: str
    laterality: str
    method: str
    repeat_index: int
    revision: int
    value_number: float | None
    unit: str | None
    source: str
    supersedes_observation_id: str | None
    record_status: str
    correction_reason: str | None = None
    finalized_by: str | None = None
    recorded_by: str
    recorded_at: datetime
    row_hash: str

    @field_validator("value_number", mode="before")
    @classmethod
    def _coerce_number(cls, value: object) -> float | None:
        if value is None:
            return None
        return float(value)


class FindingCreate(BaseModel):
    rule_id: str
    rule_version: int
    study_id: str
    target_type: str
    target_id: str
    fingerprint: str
    message_code: str
    subject_id: str | None = None
    visit_id: str | None = None
