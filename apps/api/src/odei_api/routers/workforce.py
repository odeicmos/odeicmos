"""Facility workforce registry and independent professional credential verification."""
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/workforce", tags=["workforce"])
HR_ROLES = ["facility_admin", "hr_manager"]
CREDENTIAL_REVIEW_ROLES = ["facility_admin", "clinical_governance_officer"]

class StaffCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    staff_code: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=2, max_length=160)
    work_email: str | None = Field(default=None, max_length=254)
    work_phone: str | None = Field(default=None, max_length=40)
    employment_type: Literal["permanent", "contract", "locum", "volunteer", "intern"]
    start_date: date

class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    staff_id: str = Field(min_length=1, max_length=64)
    profession: str = Field(min_length=2, max_length=120)
    registration_authority: str = Field(min_length=2, max_length=160)
    registration_number: str = Field(min_length=1, max_length=120)
    valid_until: date | None = None
    evidence_object_ref: str = Field(min_length=8, max_length=300)

class ShiftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    staff_id: str = Field(min_length=1, max_length=64)
    department_code: str = Field(min_length=1, max_length=64)
    shift_type: Literal["day", "night", "on_call", "other"]
    starts_at: datetime
    ends_at: datetime

class ShiftAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=5, max_length=1000)
class StaffDeactivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    rationale: str = Field(min_length=5, max_length=2000)


class CredentialDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    decision: Literal["verified", "rejected"]
    rationale: str = Field(min_length=5, max_length=2000)

def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db

@router.post("/staff", status_code=status.HTTP_201_CREATED)
async def create_staff(payload: StaffCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, HR_ROLES)
    if payload.start_date > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Employment start date cannot be in the future")
    staff_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {"staff_id": staff_id, "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject}
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.staff_members.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.staff.create", resource_type="staff_member", resource_id=staff_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "staff_code": payload.staff_code}, session=session)
    return {"staff_id": staff_id, "staff_code": payload.staff_code, "status": "active", "created_at": now}

@router.post("/credentials", status_code=status.HTTP_201_CREATED)
async def submit_credential(payload: CredentialCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, HR_ROLES)
    staff = await db.staff_members.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "staff_id": payload.staff_id, "status": "active"}, projection={"_id": 1})
    if staff is None:
        raise HTTPException(status_code=404, detail="Active staff member not found")
    if payload.valid_until is not None and payload.valid_until < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Expired credentials cannot be submitted as current")
    credential_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {"credential_id": credential_id, "status": "pending_verification",
        "submitted_at": now, "submitted_by_issuer": principal.issuer, "submitted_by_subject": principal.subject}
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.staff_credentials.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.credential.submit", resource_type="staff_credential", resource_id=credential_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "staff_id": payload.staff_id}, session=session)
    return {"credential_id": credential_id, "status": "pending_verification", "submitted_at": now}

@router.post("/credentials/{credential_id}/decision")
async def decide_credential(credential_id: str, payload: CredentialDecision, request: Request,
                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CREDENTIAL_REVIEW_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            credential = await db.staff_credentials.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "credential_id": credential_id,
                "status": "pending_verification"}, session=session)
            if credential is None:
                raise HTTPException(status_code=404, detail="Credential awaiting verification not found")
            if credential.get("submitted_by_issuer") == principal.issuer and credential.get("submitted_by_subject") == principal.subject:
                raise HTTPException(status_code=403, detail="Submitter cannot verify their own credential")
            if credential.get("valid_until") and credential["valid_until"] < now.date() and payload.decision == "verified":
                raise HTTPException(status_code=409, detail="Expired credential cannot be verified as current")
            changed = await db.staff_credentials.update_one({"_id": credential["_id"], "status": "pending_verification"},
                {"$set": {"status": payload.decision, "decision_rationale": payload.rationale,
                    "decided_at": now, "decided_by_issuer": principal.issuer,
                    "decided_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Credential state changed; retry")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.credential." + payload.decision, resource_type="staff_credential",
                resource_id=credential_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "staff_id": credential["staff_id"]}, session=session)
    return {"credential_id": credential_id, "status": payload.decision, "decided_at": now}

@router.post("/staff/{staff_id}/deactivate")
async def deactivate_staff(staff_id: str, payload: StaffDeactivation, request: Request,
                           principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, HR_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            staff = await db.staff_members.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "staff_id": staff_id, "status": "active"}, session=session)
            if staff is None:
                raise HTTPException(status_code=404, detail="Active staff member not found")
            changed = await db.staff_members.update_one({"_id": staff["_id"], "status": "active"},
                {"$set": {"status": "inactive", "deactivated_at": now, "deactivation_reason": payload.rationale,
                    "deactivated_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Staff status changed; retry")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.staff.deactivate", resource_type="staff_member", resource_id=staff_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id}, session=session)
    return {"staff_id": staff_id, "status": "inactive", "deactivated_at": now}

@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(payload: ShiftCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, HR_ROLES)
    if payload.starts_at.tzinfo is None or payload.starts_at.utcoffset() is None or payload.ends_at.tzinfo is None or payload.ends_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="Shift times must include timezone")
    if payload.ends_at <= payload.starts_at or payload.starts_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Shift must have a positive duration and start in the future")
    now, shift_id = datetime.now(timezone.utc), str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            staff = await db.staff_members.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "staff_id": payload.staff_id, "status": "active"}, session=session)
            if staff is None:
                raise HTTPException(status_code=404, detail="Active staff member not found")
            # Touch the staff row so concurrent roster writes for this person conflict at transaction commit.
            roster_lock = await db.staff_members.update_one({"_id": staff["_id"], "status": "active"},
                {"$inc": {"roster_revision": 1}}, session=session)
            if roster_lock.modified_count != 1:
                raise HTTPException(status_code=409, detail="Staff roster changed; retry")
            overlap = await db.staff_shifts.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "staff_id": payload.staff_id, "status": "scheduled",
                "starts_at": {"$lt": payload.ends_at}, "ends_at": {"$gt": payload.starts_at}}, session=session)
            if overlap:
                raise HTTPException(status_code=409, detail="Staff member already has an overlapping scheduled shift")
            await db.staff_shifts.insert_one(payload.model_dump() | {"shift_id": shift_id, "status": "scheduled",
                "created_at": now, "created_by_subject": principal.subject}, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.shift.create", resource_type="staff_shift", resource_id=shift_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "staff_id": payload.staff_id}, session=session)
    return {"shift_id": shift_id, "status": "scheduled", "created_at": now}

@router.post("/shifts/{shift_id}/cancel")
async def cancel_shift(shift_id: str, payload: ShiftAction, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, HR_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            shift = await db.staff_shifts.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "shift_id": shift_id, "status": "scheduled"}, session=session)
            if shift is None:
                raise HTTPException(status_code=404, detail="Scheduled shift not found")
            changed = await db.staff_shifts.update_one({"_id": shift["_id"], "status": "scheduled"},
                {"$set": {"status": "cancelled", "cancelled_at": now, "cancellation_reason": payload.reason,
                    "cancelled_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Shift state changed; retry")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="workforce.shift.cancel", resource_type="staff_shift", resource_id=shift_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "staff_id": shift["staff_id"]}, session=session)
    return {"shift_id": shift_id, "status": "cancelled", "cancelled_at": now}
