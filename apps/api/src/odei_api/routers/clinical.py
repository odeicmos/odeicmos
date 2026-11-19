"""Encounter, clinical documentation and care-plan APIs.

This is a deliberately narrow first vertical slice: every resource is tenant- and
facility-scoped, tied to an existing patient, role-gated, and audited. It is not
a substitute for specialty-specific clinical workflows or validated terminology.
"""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/clinical", tags=["clinical-records"])
CLINICAL_ROLES = ["facility_admin", "clinician", "nurse"]
ENCOUNTER_ROLES = ["facility_admin", "clinician", "nurse", "receptionist"]


class EncounterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_type: Literal["opd", "emergency", "inpatient", "procedure", "immunization", "telehealth"]
    chief_complaint: str | None = Field(default=None, max_length=2000)
    priority: Literal["routine", "urgent", "emergency"] = "routine"


class ClinicalNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    note_type: Literal["assessment", "progress", "nursing", "discharge", "procedure"]
    body: str = Field(min_length=1, max_length=20000)


class CarePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=3, max_length=200)
    goals: list[str] = Field(min_length=1, max_length=30)
    interventions: list[str] = Field(min_length=1, max_length=50)
    review_due_at: datetime | None = None


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _patient_exists(db, tenant_id: str, facility_id: str, patient_id: str) -> bool:
    return await db.patients.find_one({
        "tenant_id": tenant_id, "facility_id": facility_id,
        "patient_id": patient_id, "record_status": "active",
    }, projection={"_id": 1}) is not None


@router.post("/encounters", status_code=status.HTTP_201_CREATED)
async def create_encounter(
    payload: EncounterCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    role = await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, ENCOUNTER_ROLES
    )
    if not await _patient_exists(db, payload.tenant_id, payload.facility_id, payload.patient_id):
        raise HTTPException(status_code=404, detail="Active patient not found in this facility")
    encounter_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "encounter_id": encounter_id, "status": "open",
        "started_at": now, "created_at": now,
        "created_by_issuer": principal.issuer,
        "created_by_subject": principal.subject,
    }
    try:
        client = request.app.state.mongo_client
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db.encounters.insert_one(record, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="encounter.create", resource_type="encounter",
                    resource_id=encounter_id, tenant_id=payload.tenant_id,
                    outcome="success", metadata={"facility_id": payload.facility_id, "role": role},
                    session=session,
                )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Encounter identifier conflict") from exc
    return {"encounter_id": encounter_id, "patient_id": payload.patient_id,
            "status": "open", "started_at": now}


@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def add_clinical_note(
    payload: ClinicalNoteCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, CLINICAL_ROLES
    )
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "encounter_id": payload.encounter_id, "status": "open",
    }, projection={"_id": 0, "patient_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open encounter not found")
    note_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "note_id": note_id, "patient_id": encounter["patient_id"],
        "created_at": now, "author_issuer": principal.issuer,
        "author_subject": principal.subject, "status": "signed",
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.clinical_notes.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="clinical_note.create", resource_type="clinical_note",
                resource_id=note_id, tenant_id=payload.tenant_id,
                outcome="success", metadata={"facility_id": payload.facility_id,
                "encounter_id": payload.encounter_id}, session=session,
            )
    return {"note_id": note_id, "encounter_id": payload.encounter_id,
            "status": "signed", "created_at": now}


@router.post("/care-plans", status_code=status.HTTP_201_CREATED)
async def create_care_plan(
    payload: CarePlanCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, CLINICAL_ROLES
    )
    if not await _patient_exists(db, payload.tenant_id, payload.facility_id, payload.patient_id):
        raise HTTPException(status_code=404, detail="Active patient not found in this facility")
    if payload.encounter_id is not None:
        encounter = await db.encounters.find_one({
            "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
            "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
        }, projection={"_id": 1})
        if encounter is None:
            raise HTTPException(status_code=404, detail="Encounter not found for this patient")
    plan_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "care_plan_id": plan_id, "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.care_plans.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="care_plan.create", resource_type="care_plan",
                resource_id=plan_id, tenant_id=payload.tenant_id,
                outcome="success", metadata={"facility_id": payload.facility_id},
                session=session,
            )
    return {"care_plan_id": plan_id, "patient_id": payload.patient_id,
            "status": "active", "created_at": now}
