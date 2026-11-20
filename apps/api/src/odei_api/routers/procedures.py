"""Procedure request, safety checklist, time-out and completion record."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/procedures", tags=["procedures"])
PROCEDURE_ROLES = ["facility_admin", "clinician", "nurse"]
PERFORMER_ROLES = ["facility_admin", "clinician"]


class ProcedureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    procedure_code: str = Field(min_length=1, max_length=80)
    procedure_name: str = Field(min_length=2, max_length=200)
    indication: str = Field(min_length=3, max_length=2000)
    body_site: str | None = Field(default=None, max_length=160)
    laterality: Literal["left", "right", "bilateral", "not_applicable"] = "not_applicable"
    planned_at: datetime
    requires_consent: bool = True

    @field_validator("planned_at")
    @classmethod
    def planned_at_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("planned_at must include timezone")
        return value


class ProcedureSafetyChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_identity_verified: bool
    procedure_and_site_confirmed: bool
    consent_status: Literal["obtained", "not_required", "deferred"]
    consent_evidence_reference: str | None = Field(default=None, max_length=500)
    allergies_reviewed: bool
    equipment_and_supplies_checked: bool
    infection_prevention_ready: bool
    site_marking_status: Literal["completed", "not_indicated", "not_completed"]
    checklist_note: str = Field(min_length=3, max_length=2000)


class ProcedureStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    time_out_confirmed: bool
    team_members: list[str] = Field(min_length=1, max_length=20)
    start_note: str = Field(min_length=3, max_length=1000)


class ProcedureCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    outcome: Literal["completed", "abandoned", "converted_to_other_procedure"]
    performed_at: datetime
    findings: str = Field(min_length=2, max_length=4000)
    complications: str = Field(min_length=2, max_length=2000)
    post_procedure_plan: str = Field(min_length=2, max_length=3000)

    @field_validator("performed_at")
    @classmethod
    def performed_at_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("performed_at must include timezone")
        return value


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, procedure_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}", action=action,
        resource_type="procedure", resource_id=procedure_id, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id, **(metadata or {})},
        session=session,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def request_procedure(payload: ProcedureRequest, request: Request,
                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, PERFORMER_ROLES)
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
        "status": "open",
    }, projection={"_id": 1})
    if patient is None or encounter is None:
        raise HTTPException(status_code=404, detail="Active patient and matching open encounter are required")
    now = datetime.now(timezone.utc)
    if payload.planned_at < now:
        raise HTTPException(status_code=422, detail="Planned procedure time cannot be in the past")
    procedure_id = str(uuid4())
    record = payload.model_dump() | {
        "procedure_id": procedure_id, "status": "requested",
        "created_at": now, "requested_by_issuer": principal.issuer,
        "requested_by_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.procedures.insert_one(record, session=session)
            await _audit(db, session, principal, "procedure.request", procedure_id,
                         payload.tenant_id, payload.facility_id,
                         {"patient_id": payload.patient_id, "procedure_code": payload.procedure_code})
    return {"procedure_id": procedure_id, "status": "requested", "created_at": now}


@router.post("/{procedure_id}/safety-checklist")
async def record_procedure_safety_checklist(procedure_id: str, payload: ProcedureSafetyChecklist,
                                            request: Request,
                                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, PROCEDURE_ROLES)
    if not payload.patient_identity_verified or not payload.procedure_and_site_confirmed:
        raise HTTPException(status_code=422, detail="Identity and procedure/site confirmation are mandatory")
    if payload.consent_status == "deferred":
        raise HTTPException(status_code=422, detail="Deferred consent does not permit procedure readiness")
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            procedure = await db.procedures.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "procedure_id": procedure_id, "status": "requested",
            }, session=session)
            if procedure is None:
                raise HTTPException(status_code=404, detail="Requested procedure not found")
            if procedure["requires_consent"] and payload.consent_status != "obtained":
                raise HTTPException(status_code=422, detail="Documented consent is required for this procedure")
            if payload.consent_status == "obtained" and not payload.consent_evidence_reference:
                raise HTTPException(status_code=422, detail="Consent evidence reference is required")
            if payload.consent_status == "not_required" and procedure["requires_consent"]:
                raise HTTPException(status_code=422, detail="This procedure requires consent")
            if not all([payload.allergies_reviewed, payload.equipment_and_supplies_checked,
                        payload.infection_prevention_ready]):
                raise HTTPException(status_code=422, detail="All required safety checks must be completed")
            if procedure["laterality"] != "not_applicable" and payload.site_marking_status != "completed":
                raise HTTPException(status_code=422, detail="Site marking is required for this laterality")
            checklist_id = str(uuid4())
            await db.procedure_safety_checks.insert_one(payload.model_dump() | {
                "checklist_id": checklist_id, "procedure_id": procedure_id,
                "patient_id": procedure["patient_id"], "recorded_at": now,
                "recorded_by_issuer": principal.issuer, "recorded_by_subject": principal.subject,
            }, session=session)
            changed = await db.procedures.update_one(
                {"_id": procedure["_id"], "status": "requested"},
                {"$set": {"status": "ready_for_time_out", "checklist_id": checklist_id,
                          "checklist_recorded_at": now}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Procedure state changed; retry after reload")
            await _audit(db, session, principal, "procedure.safety_checklist", procedure_id,
                         payload.tenant_id, payload.facility_id, {"checklist_id": checklist_id})
    return {"procedure_id": procedure_id, "status": "ready_for_time_out", "checklist_id": checklist_id}


@router.post("/{procedure_id}/start")
async def start_procedure(procedure_id: str, payload: ProcedureStart, request: Request,
                          principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, PERFORMER_ROLES)
    if not payload.time_out_confirmed:
        raise HTTPException(status_code=422, detail="Team time-out must be confirmed before starting")
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            procedure = await db.procedures.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "procedure_id": procedure_id, "status": "ready_for_time_out",
            }, session=session)
            if procedure is None:
                raise HTTPException(status_code=404, detail="Procedure is not ready to start")
            changed = await db.procedures.update_one(
                {"_id": procedure["_id"], "status": "ready_for_time_out"},
                {"$set": {"status": "in_progress", "time_out_confirmed": True,
                          "team_members": payload.team_members, "start_note": payload.start_note,
                          "started_at": now, "started_by_issuer": principal.issuer,
                          "started_by_subject": principal.subject}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Procedure state changed; retry after reload")
            await _audit(db, session, principal, "procedure.start", procedure_id,
                         payload.tenant_id, payload.facility_id)
    return {"procedure_id": procedure_id, "status": "in_progress", "started_at": now}


@router.post("/{procedure_id}/complete")
async def complete_procedure(procedure_id: str, payload: ProcedureCompletion, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, PERFORMER_ROLES)
    now = datetime.now(timezone.utc)
    if payload.performed_at > now:
        raise HTTPException(status_code=422, detail="Procedure completion time cannot be in the future")
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            procedure = await db.procedures.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "procedure_id": procedure_id, "status": "in_progress",
            }, session=session)
            if procedure is None:
                raise HTTPException(status_code=404, detail="In-progress procedure not found")
            changed = await db.procedures.update_one(
                {"_id": procedure["_id"], "status": "in_progress"},
                {"$set": {"status": "completed" if payload.outcome == "completed" else "not_completed", "outcome": payload.outcome,
                          "performed_at": payload.performed_at, "findings": payload.findings,
                          "complications": payload.complications, "post_procedure_plan": payload.post_procedure_plan,
                          "completed_at": now, "completed_by_issuer": principal.issuer,
                          "completed_by_subject": principal.subject}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Procedure state changed; retry after reload")
            await _audit(db, session, principal, "procedure.complete", procedure_id,
                         payload.tenant_id, payload.facility_id, {"outcome": payload.outcome})
    return {"procedure_id": procedure_id, "status": "completed" if payload.outcome == "completed" else "not_completed", "outcome": payload.outcome}
