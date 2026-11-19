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


class ClinicalNoteAmendmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=5, max_length=1000)
    body: str = Field(min_length=1, max_length=20000)


class NoteSign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)


class TriageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    acuity: int = Field(ge=1, le=5)
    presenting_concern: str = Field(min_length=2, max_length=2000)
    temperature_c: float | None = Field(default=None, ge=25, le=45)
    pulse_bpm: int | None = Field(default=None, ge=0, le=300)
    respiratory_rate: int | None = Field(default=None, ge=0, le=100)
    systolic_bp_mmhg: int | None = Field(default=None, ge=0, le=300)
    diastolic_bp_mmhg: int | None = Field(default=None, ge=0, le=200)
    oxygen_saturation_pct: float | None = Field(default=None, ge=0, le=100)
    weight_kg: float | None = Field(default=None, gt=0, le=500)
    height_cm: float | None = Field(default=None, gt=0, le=300)



class TriageReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reviewed_acuity: int = Field(ge=1, le=5)
    disposition: Literal["routine_queue", "urgent_review", "emergency_response", "referred"]
    rationale: str = Field(min_length=5, max_length=2000)
    override_reason: str | None = Field(default=None, max_length=1000)

class ObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=80)
    display: str = Field(min_length=2, max_length=160)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    effective_at: datetime | None = None


class DiagnosisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    code_system: str = Field(min_length=3, max_length=200)
    code: str = Field(min_length=1, max_length=80)
    display: str = Field(min_length=2, max_length=200)
    clinical_status: Literal["active", "resolved", "provisional"] = "active"
    primary: bool = False


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
        "author_subject": principal.subject, "status": "draft",
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
            "status": "draft", "created_at": now}


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

 
@router.post("/triage", status_code=status.HTTP_201_CREATED)
async def create_triage(payload: TriageCreate, request: Request,
                        principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    ["facility_admin", "nurse", "clinician"])
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "encounter_id": payload.encounter_id, "status": "open",
    }, projection={"_id": 1, "patient_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open encounter not found")
    triage_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "triage_id": triage_id, "patient_id": encounter["patient_id"],
        "recorded_at": now, "review_status": "awaiting_review", "recorded_by_issuer": principal.issuer,
        "recorded_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.triage_assessments.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="triage.create", resource_type="triage_assessment",
                resource_id=triage_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "encounter_id": payload.encounter_id,
                          "acuity": payload.acuity}, session=session)
    return {"triage_id": triage_id, "encounter_id": payload.encounter_id,
            "acuity": payload.acuity, "recorded_at": now}


@router.post("/observations", status_code=status.HTTP_201_CREATED)
async def create_observation(payload: ObservationCreate, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CLINICAL_ROLES)
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "encounter_id": payload.encounter_id, "status": "open",
    }, projection={"_id": 1, "patient_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open encounter not found")
    if payload.effective_at is not None and (payload.effective_at.tzinfo is None or payload.effective_at.utcoffset() is None):
        raise HTTPException(status_code=422, detail="effective_at must include timezone")
    observation_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "observation_id": observation_id, "patient_id": encounter["patient_id"],
        "effective_at": payload.effective_at or now, "recorded_at": now,
        "recorder_issuer": principal.issuer, "recorder_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.observations.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="observation.create", resource_type="observation",
                resource_id=observation_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "encounter_id": payload.encounter_id,
                          "code": payload.code}, session=session)
    return {"observation_id": observation_id, "encounter_id": payload.encounter_id,
            "recorded_at": now}


@router.post("/diagnoses", status_code=status.HTTP_201_CREATED)
async def create_diagnosis(payload: DiagnosisCreate, request: Request,
                           principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    ["facility_admin", "clinician"])
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "encounter_id": payload.encounter_id, "status": "open",
    }, projection={"_id": 1, "patient_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open encounter not found")
    diagnosis_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "diagnosis_id": diagnosis_id, "patient_id": encounter["patient_id"],
        "recorded_at": now, "recorder_issuer": principal.issuer,
        "recorder_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.diagnoses.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="diagnosis.create", resource_type="diagnosis",
                resource_id=diagnosis_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "encounter_id": payload.encounter_id,
                          "code": payload.code}, session=session)
    return {"diagnosis_id": diagnosis_id, "encounter_id": payload.encounter_id,
            "clinical_status": payload.clinical_status, "recorded_at": now}


@router.post("/notes/{note_id}/sign")
async def sign_clinical_note(note_id: str, payload: NoteSign, request: Request,
                             principal: Principal = Depends(require_principal)):
    tenant_id, facility_id = payload.tenant_id, payload.facility_id
    db = _db(request)
    role = await authorize_facility_access(
        request, principal, tenant_id, facility_id,
        ["facility_admin", "clinician", "nurse"],
    )
    note = await db.clinical_notes.find_one({
        "tenant_id": tenant_id, "facility_id": facility_id, "note_id": note_id,
        "status": "draft",
    })
    if note is None:
        raise HTTPException(status_code=404, detail="Draft clinical note not found")
    is_author = note["author_issuer"] == principal.issuer and note["author_subject"] == principal.subject
    if not is_author and role not in ["facility_admin", "clinician"]:
        raise HTTPException(status_code=403, detail="Only the author or an authorized clinician may sign")
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            changed = await db.clinical_notes.update_one(
                {"_id": note["_id"], "status": "draft"},
                {"$set": {"status": "signed", "signed_at": now,
                          "signer_issuer": principal.issuer, "signer_subject": principal.subject}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Note state changed; reload before signing")
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="clinical_note.sign", resource_type="clinical_note",
                resource_id=note_id, tenant_id=tenant_id, outcome="success",
                metadata={"facility_id": facility_id, "encounter_id": note["encounter_id"]},
                session=session,
            )
    return {"note_id": note_id, "status": "signed", "signed_at": now}


@router.post("/notes/{note_id}/amendments", status_code=status.HTTP_201_CREATED)
async def amend_signed_clinical_note(
    note_id: str, payload: ClinicalNoteAmendmentCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    """Append a separately signed correction; never rewrite the original signed note."""
    db = _db(request)
    role = await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["facility_admin", "clinician"],
    )
    amendment_id, now = str(uuid4()), datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            note = await db.clinical_notes.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "note_id": note_id, "status": "signed",
            }, session=session)
            if note is None:
                raise HTTPException(status_code=404, detail="Signed clinical note not found")
            version = int(note.get("amendment_count", 0)) + 1
            changed = await db.clinical_notes.update_one(
                {"_id": note["_id"], "status": "signed",
                 "$or": [{"amendment_count": note.get("amendment_count", 0)}, {"amendment_count": {"$exists": False}}]},
                {"$inc": {"amendment_count": 1}, "$set": {"last_amended_at": now}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Note amendment conflict; reload and retry")
            await db.clinical_note_amendments.insert_one({
                "amendment_id": amendment_id, "note_id": note_id,
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "patient_id": note["patient_id"], "encounter_id": note["encounter_id"],
                "version": version, "reason": payload.reason, "body": payload.body,
                "created_at": now, "author_issuer": principal.issuer,
                "author_subject": principal.subject, "status": "signed",
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="clinical_note.amend", resource_type="clinical_note",
                resource_id=note_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "amendment_id": amendment_id,
                          "version": version, "role": role}, session=session,
            )
    return {"note_id": note_id, "amendment_id": amendment_id,
            "version": version, "status": "signed", "created_at": now}

@router.post("/triage/{triage_id}/review")
async def review_triage(triage_id: str, payload: TriageReviewCreate, request: Request,
                        principal: Principal = Depends(require_principal)):
    """Qualified human review and disposition; no automated acuity decision is made."""
    db = _db(request)
    role = await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["facility_admin", "nurse", "clinician"],
    )
    if payload.reviewed_acuity != 1 and payload.disposition == "emergency_response":
        raise HTTPException(status_code=422, detail="Emergency response requires highest acuity (1)")
    if payload.reviewed_acuity != 5 and payload.disposition == "routine_queue":
        raise HTTPException(status_code=422, detail="Routine queue requires lowest acuity (5)")
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            triage = await db.triage_assessments.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "triage_id": triage_id, "review_status": "awaiting_review",
            }, session=session)
            if triage is None:
                raise HTTPException(status_code=404, detail="Triage awaiting review not found")
            if payload.reviewed_acuity != triage["acuity"] and not payload.override_reason:
                raise HTTPException(status_code=422, detail="Acuity change requires an override reason")
            changed = await db.triage_assessments.update_one(
                {"_id": triage["_id"], "review_status": "awaiting_review"},
                {"$set": {
                    "review_status": "reviewed", "reviewed_acuity": payload.reviewed_acuity,
                    "disposition": payload.disposition, "review_rationale": payload.rationale,
                    "override_reason": payload.override_reason, "reviewed_at": now,
                    "reviewer_issuer": principal.issuer, "reviewer_subject": principal.subject,
                }}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Triage review conflict; reload and retry")
            priority = "emergency" if payload.disposition == "emergency_response" else (
                "urgent" if payload.disposition == "urgent_review" else "routine"
            )
            await db.encounters.update_one(
                {"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                 "encounter_id": triage["encounter_id"], "status": "open"},
                {"$set": {"priority": priority, "triage_reviewed_at": now}}, session=session,
            )
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="triage.review", resource_type="triage_assessment",
                resource_id=triage_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "role": role,
                          "disposition": payload.disposition,
                          "reviewed_acuity": payload.reviewed_acuity}, session=session,
            )
    return {"triage_id": triage_id, "review_status": "reviewed",
            "disposition": payload.disposition, "reviewed_at": now}

