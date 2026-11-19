"""Appointment booking, check-in and cancellation foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/appointments", tags=["appointments"])
BOOKING_ROLES = ["facility_admin", "receptionist", "clinician"]
DESK_ROLES = ["facility_admin", "receptionist", "nurse"]


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    starts_at: datetime
    ends_at: datetime
    service_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=2, max_length=1000)
    practitioner_subject: str | None = Field(default=None, max_length=200)
    appointment_type: Literal["consultation", "review", "procedure", "immunization", "telehealth"] = "consultation"

    @model_validator(mode="after")
    def validate_times(self):
        for value in (self.starts_at, self.ends_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Appointment times must include timezone")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AppointmentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reason: str | None = Field(default=None, max_length=1000)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, appointment_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
        action=action, resource_type="appointment", resource_id=appointment_id,
        tenant_id=tenant_id, outcome="success",
        metadata={"facility_id": facility_id, **(metadata or {})}, session=session)


@router.post("", status_code=status.HTTP_201_CREATED)
async def book_appointment(payload: AppointmentCreate, request: Request,
                           principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, BOOKING_ROLES)
    patient = await db.patients.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "patient_id": payload.patient_id,
        "record_status": "active"}, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Active patient not found")
    appointment_id, now = str(uuid4()), datetime.now(timezone.utc)
    if payload.starts_at <= now:
        raise HTTPException(status_code=422, detail="New appointments must start in the future")
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            if payload.practitioner_subject:
                conflict = await db.appointments.find_one({
                    "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                    "practitioner_subject": payload.practitioner_subject,
                    "status": {"$in": ["booked", "checked_in"]},
                    "starts_at": {"$lt": payload.ends_at}, "ends_at": {"$gt": payload.starts_at},
                }, session=session, projection={"_id": 1})
                if conflict:
                    raise HTTPException(status_code=409, detail="Practitioner has an overlapping appointment")
            await db.appointments.insert_one(payload.model_dump() | {
                "appointment_id": appointment_id, "status": "booked",
                "created_at": now, "created_by_issuer": principal.issuer,
                "created_by_subject": principal.subject,
            }, session=session)
            await _audit(db, session, principal, "appointment.book", appointment_id,
                         payload.tenant_id, payload.facility_id,
                         {"patient_id": payload.patient_id, "starts_at": payload.starts_at})
    return {"appointment_id": appointment_id, "status": "booked", "created_at": now}


@router.post("/{appointment_id}/check-in")
async def check_in_appointment(appointment_id: str, payload: AppointmentAction, request: Request,
                              principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, DESK_ROLES)
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            appointment = await db.appointments.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "appointment_id": appointment_id,
                "status": "booked"}, session=session)
            if appointment is None:
                raise HTTPException(status_code=404, detail="Booked appointment not found")
            changed = await db.appointments.update_one({"_id": appointment["_id"], "status": "booked"},
                {"$set": {"status": "checked_in", "checked_in_at": now,
                          "checked_in_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Appointment state changed; retry")
            await _audit(db, session, principal, "appointment.check_in", appointment_id,
                         payload.tenant_id, payload.facility_id)
    return {"appointment_id": appointment_id, "status": "checked_in", "checked_in_at": now}


@router.post("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: str, payload: AppointmentAction, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, BOOKING_ROLES)
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            appointment = await db.appointments.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "appointment_id": appointment_id,
                "status": {"$in": ["booked", "checked_in"]}}, session=session)
            if appointment is None:
                raise HTTPException(status_code=404, detail="Active appointment not found")
            changed = await db.appointments.update_one({"_id": appointment["_id"],
                "status": appointment["status"]}, {"$set": {"status": "cancelled",
                "cancelled_at": now, "cancellation_reason": payload.reason,
                "cancelled_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Appointment state changed; retry")
            await _audit(db, session, principal, "appointment.cancel", appointment_id,
                         payload.tenant_id, payload.facility_id, {"reason": payload.reason})
    return {"appointment_id": appointment_id, "status": "cancelled", "cancelled_at": now}
