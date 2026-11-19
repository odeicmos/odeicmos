"""Immunization administration and adverse-event reporting foundation."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/immunization", tags=["immunization"])
ADMIN_ROLES = ["facility_admin", "vaccinator", "nurse"]
REPORT_ROLES = ["facility_admin", "vaccinator", "nurse", "clinician"]


class ImmunizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str | None = Field(default=None, max_length=64)
    vaccine_code: str = Field(min_length=1, max_length=80)
    vaccine_name: str = Field(min_length=2, max_length=160)
    dose_number: int = Field(ge=1, le=20)
    administered_at: datetime
    batch_number: str = Field(min_length=1, max_length=100)
    expiry_date: date
    dose_quantity: str = Field(min_length=1, max_length=40)
    route: str = Field(min_length=1, max_length=60)
    site: str | None = Field(default=None, max_length=100)

    @field_validator("administered_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("administered_at must include a timezone")
        return value


class AdverseEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    immunization_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=5, max_length=5000)
    severity: Literal["non_serious", "serious", "life_threatening", "fatal"]
    onset_at: datetime | None = None
    outcome: str | None = Field(default=None, max_length=500)

    @field_validator("onset_at")
    @classmethod
    def require_timezone_when_present(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("onset_at must include a timezone")
        return value


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/administrations", status_code=status.HTTP_201_CREATED)
async def record_immunization(
    payload: ImmunizationCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ADMIN_ROLES)
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Active patient not found")
    if payload.expiry_date < payload.administered_at.date():
        raise HTTPException(status_code=422, detail="Vaccine batch was expired at administration time")
    if payload.administered_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Administration time cannot be in the future")
    if payload.encounter_id is not None:
        encounter = await db.encounters.find_one({
            "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
            "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
        }, projection={"_id": 1})
        if encounter is None:
            raise HTTPException(status_code=404, detail="Encounter not found for patient")
    immunization_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "immunization_id": immunization_id, "status": "completed",
        "recorded_at": now, "recorder_issuer": principal.issuer,
        "recorder_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.immunizations.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="immunization.record", resource_type="immunization",
                resource_id=immunization_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "vaccine_code": payload.vaccine_code},
                session=session,
            )
    return {"immunization_id": immunization_id, "status": "completed", "recorded_at": now}


@router.post("/adverse-events", status_code=status.HTTP_201_CREATED)
async def report_adverse_event(
    payload: AdverseEventCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, REPORT_ROLES)
    immunization = await db.immunizations.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "immunization_id": payload.immunization_id,
    }, projection={"_id": 1, "patient_id": 1})
    if immunization is None:
        raise HTTPException(status_code=404, detail="Immunization record not found")
    event_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "adverse_event_id": event_id, "patient_id": immunization["patient_id"],
        "status": "reported", "reported_at": now,
        "reporter_issuer": principal.issuer, "reporter_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.immunization_adverse_events.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="immunization_adverse_event.report", resource_type="immunization_adverse_event",
                resource_id=event_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "severity": payload.severity},
                session=session,
            )
    return {"adverse_event_id": event_id, "status": "reported", "reported_at": now}
