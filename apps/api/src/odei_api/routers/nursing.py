"""Nursing task and shift-handover workflows with append-only acknowledgement."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/nursing", tags=["nursing"])
NURSING_ROLES = ["facility_admin", "nurse"]
CLINICAL_ROLES = ["facility_admin", "nurse", "clinician"]


class NursingTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    admission_id: str | None = Field(default=None, max_length=64)
    category: Literal["assessment", "monitoring", "hygiene", "mobility", "wound_care",
                      "nutrition", "education", "specimen", "other"]
    instruction: str = Field(min_length=3, max_length=2000)
    priority: Literal["routine", "urgent", "time_critical"] = "routine"
    due_at: datetime
    assigned_to_subject: str | None = Field(default=None, max_length=256)

    @field_validator("due_at")
    @classmethod
    def due_at_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must include timezone")
        return value


class NursingTaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    outcome: Literal["completed", "not_done", "cancelled"]
    outcome_note: str = Field(min_length=3, max_length=2000)


class HandoverCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    admission_id: str | None = Field(default=None, max_length=64)
    situation: str = Field(min_length=2, max_length=2000)
    background: str = Field(min_length=2, max_length=3000)
    assessment: str = Field(min_length=2, max_length=3000)
    recommendations: str = Field(min_length=2, max_length=3000)
    outstanding_actions: list[str] = Field(default_factory=list, max_length=30)
    risk_flags: list[Literal["falls", "pressure_injury", "allergy", "infection",
                             "deterioration", "self_harm", "safeguarding", "other"]] = Field(
                                 default_factory=list, max_length=20)


class HandoverAcknowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    acknowledgement_note: str = Field(min_length=2, max_length=1000)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, kind, resource_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}", action=action,
        resource_type=kind, resource_id=resource_id, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id, **(metadata or {})},
        session=session,
    )


async def _active_patient_encounter(db, payload):
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
        "status": "open",
    }, projection={"_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open patient encounter not found")
    if payload.admission_id is not None:
        admission = await db.admissions.find_one({
            "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
            "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
            "admission_id": payload.admission_id, "status": "admitted",
        }, projection={"_id": 1})
        if admission is None:
            raise HTTPException(status_code=404, detail="Active inpatient admission not found")


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_nursing_task(payload: NursingTaskCreate, request: Request,
                              principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id,
                                    payload.facility_id, CLINICAL_ROLES)
    await _active_patient_encounter(db, payload)
    task_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "task_id": task_id, "status": "pending", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.nursing_tasks.insert_one(record, session=session)
            await _audit(db, session, principal, "nursing.task.create", "nursing_task",
                         task_id, payload.tenant_id, payload.facility_id,
                         {"patient_id": payload.patient_id, "priority": payload.priority})
    return {"task_id": task_id, "status": "pending", "created_at": now}


@router.post("/tasks/{task_id}/outcome")
async def record_nursing_task_outcome(task_id: str, payload: NursingTaskOutcome,
                                      request: Request,
                                      principal: Principal = Depends(require_principal)):
    db = _db(request)
    role = await authorize_facility_access(request, principal, payload.tenant_id,
                                           payload.facility_id, NURSING_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            task = await db.nursing_tasks.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "task_id": task_id, "status": "pending",
            }, session=session)
            if task is None:
                raise HTTPException(status_code=404, detail="Pending nursing task not found")
            if task.get("assigned_to_subject") and task["assigned_to_subject"] != principal.subject:
                if role != "facility_admin":
                    raise HTTPException(status_code=403, detail="Task is assigned to another staff member")
            if payload.outcome == "not_done" and len(payload.outcome_note.strip()) < 5:
                raise HTTPException(status_code=422, detail="A reason is required when a task is not done")
            changed = await db.nursing_tasks.update_one(
                {"_id": task["_id"], "status": "pending"},
                {"$set": {"status": payload.outcome, "outcome_note": payload.outcome_note,
                          "completed_at": now, "completed_by_issuer": principal.issuer,
                          "completed_by_subject": principal.subject}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Task state changed; reload before retrying")
            await _audit(db, session, principal, "nursing.task.outcome", "nursing_task",
                         task_id, payload.tenant_id, payload.facility_id,
                         {"outcome": payload.outcome, "role": role})
    return {"task_id": task_id, "status": payload.outcome, "recorded_at": now}


@router.post("/handovers", status_code=status.HTTP_201_CREATED)
async def create_nursing_handover(payload: HandoverCreate, request: Request,
                                  principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id,
                                    payload.facility_id, NURSING_ROLES)
    await _active_patient_encounter(db, payload)
    handover_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "handover_id": handover_id, "status": "awaiting_acknowledgement",
        "created_at": now, "author_issuer": principal.issuer,
        "author_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.nursing_handovers.insert_one(record, session=session)
            await _audit(db, session, principal, "nursing.handover.create", "nursing_handover",
                         handover_id, payload.tenant_id, payload.facility_id,
                         {"patient_id": payload.patient_id, "risk_flags": payload.risk_flags})
    return {"handover_id": handover_id, "status": record["status"], "created_at": now}


@router.post("/handovers/{handover_id}/acknowledge")
async def acknowledge_nursing_handover(handover_id: str, payload: HandoverAcknowledge,
                                       request: Request,
                                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id,
                                    payload.facility_id, NURSING_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            handover = await db.nursing_handovers.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "handover_id": handover_id, "status": "awaiting_acknowledgement",
            }, session=session)
            if handover is None:
                raise HTTPException(status_code=404, detail="Handover awaiting acknowledgement not found")
            if handover["author_issuer"] == principal.issuer and handover["author_subject"] == principal.subject:
                raise HTTPException(status_code=403, detail="Handover author cannot acknowledge their own handover")
            changed = await db.nursing_handovers.update_one(
                {"_id": handover["_id"], "status": "awaiting_acknowledgement"},
                {"$set": {"status": "acknowledged", "acknowledgement_note": payload.acknowledgement_note,
                          "acknowledged_at": now, "acknowledger_issuer": principal.issuer,
                          "acknowledger_subject": principal.subject}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Handover state changed; reload before retrying")
            await _audit(db, session, principal, "nursing.handover.acknowledge",
                         "nursing_handover", handover_id, payload.tenant_id, payload.facility_id)
    return {"handover_id": handover_id, "status": "acknowledged", "acknowledged_at": now}
