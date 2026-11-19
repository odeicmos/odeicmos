"""Reception appointments, check-in and operational queue foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/reception", tags=["reception"])
DESK_ROLES = ["facility_admin", "receptionist"]
QUEUE_ROLES = ["facility_admin", "receptionist", "nurse", "clinician"]


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    appointment_type: str = Field(min_length=2, max_length=100)
    scheduled_start: datetime
    scheduled_end: datetime
    reason: str | None = Field(default=None, max_length=1000)
    provider_subject: str | None = Field(default=None, max_length=200)
    department_code: str | None = Field(default=None, max_length=64)

    @classmethod
    def validate_schedule(cls, values):
        return values


class CheckInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)


class QueueTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    status: Literal["in_service", "completed", "cancelled"]
    reason: str | None = Field(default=None, max_length=500)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/appointments", status_code=status.HTTP_201_CREATED)
async def create_appointment(payload: AppointmentCreate, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, DESK_ROLES)
    if payload.scheduled_start.tzinfo is None or payload.scheduled_start.utcoffset() is None:
        raise HTTPException(status_code=422, detail="scheduled_start must include a timezone")
    if payload.scheduled_end.tzinfo is None or payload.scheduled_end.utcoffset() is None:
        raise HTTPException(status_code=422, detail="scheduled_end must include a timezone")
    if payload.scheduled_end <= payload.scheduled_start:
        raise HTTPException(status_code=422, detail="scheduled_end must be after scheduled_start")
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Active patient not found")
    appointment_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "appointment_id": appointment_id, "status": "booked",
        "created_at": now, "created_by_issuer": principal.issuer,
        "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.appointments.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="appointment.create", resource_type="appointment",
                resource_id=appointment_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "patient_id": payload.patient_id},
                session=session,
            )
    return {"appointment_id": appointment_id, "status": "booked", "created_at": now}


@router.post("/appointments/{appointment_id}/check-in", status_code=status.HTTP_201_CREATED)
async def check_in_appointment(appointment_id: str, payload: CheckInRequest,
                               request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, DESK_ROLES)
    now, queue_id = datetime.now(timezone.utc), str(uuid4())
    client = request.app.state.mongo_client
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                appointment = await db.appointments.find_one({
                    "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                    "appointment_id": appointment_id, "status": "booked",
                }, session=session)
                if appointment is None:
                    raise HTTPException(status_code=404, detail="Booked appointment not found")
                changed = await db.appointments.update_one(
                    {"_id": appointment["_id"], "status": "booked"},
                    {"$set": {"status": "arrived", "checked_in_at": now}}, session=session,
                )
                if changed.modified_count != 1:
                    raise HTTPException(status_code=409, detail="Appointment check-in conflict")
                await db.queue_entries.insert_one({
                    "queue_id": queue_id, "appointment_id": appointment_id,
                    "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                    "patient_id": appointment["patient_id"], "status": "waiting",
                    "priority": "routine", "arrived_at": now,
                    "department_code": appointment.get("department_code"),
                    "created_by_subject": principal.subject,
                }, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="appointment.check_in", resource_type="appointment",
                    resource_id=appointment_id, tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id, "queue_id": queue_id},
                    session=session,
                )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Appointment already has a queue entry") from exc
    return {"appointment_id": appointment_id, "queue_id": queue_id,
            "appointment_status": "arrived", "queue_status": "waiting", "arrived_at": now}


@router.post("/queue/{queue_id}/transition")
async def transition_queue_entry(queue_id: str, payload: QueueTransition,
                                 request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, QUEUE_ROLES)
    now = datetime.now(timezone.utc)
    allowed = {"waiting": {"in_service", "cancelled"}, "in_service": {"waiting", "completed", "cancelled"}}
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            entry = await db.queue_entries.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "queue_id": queue_id,
            }, session=session)
            if entry is None:
                raise HTTPException(status_code=404, detail="Queue entry not found")
            if payload.status not in allowed.get(entry["status"], set()):
                raise HTTPException(status_code=409, detail="Invalid queue state transition")
            changed = await db.queue_entries.update_one(
                {"_id": entry["_id"], "status": entry["status"]},
                {"$set": {"status": payload.status, "updated_at": now,
                          "last_transition_reason": payload.reason,
                          "updated_by_subject": principal.subject}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Queue entry changed; retry")
            if payload.status == "in_service":
                await db.appointments.update_one(
                    {"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                     "appointment_id": entry["appointment_id"], "status": "arrived"},
                    {"$set": {"status": "in_service", "service_started_at": now}}, session=session,
                )
            elif payload.status == "completed":
                await db.appointments.update_one(
                    {"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                     "appointment_id": entry["appointment_id"], "status": "in_service"},
                    {"$set": {"status": "completed", "completed_at": now}}, session=session,
                )
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="queue.transition", resource_type="queue_entry",
                resource_id=queue_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "from": entry["status"],
                          "to": payload.status}, session=session,
            )
    return {"queue_id": queue_id, "status": payload.status, "updated_at": now}
