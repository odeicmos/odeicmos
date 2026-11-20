"""Referral lifecycle with facility scope, independent receiving decision and audit trail."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/referrals", tags=["referrals"])
REFERRAL_CREATE_ROLES = ["facility_admin", "clinician"]
REFERRAL_RECEIVE_ROLES = ["facility_admin", "clinician"]


class ReferralCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    referral_type: Literal["internal", "external"]
    specialty: str = Field(min_length=2, max_length=160)
    destination_facility: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=5, max_length=3000)
    clinical_question: str = Field(min_length=3, max_length=2000)
    urgency: Literal["routine", "urgent", "emergency"]
    requested_at: datetime
    relevant_history: str | None = Field(default=None, max_length=5000)
    requested_investigations: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("requested_at")
    @classmethod
    def requested_at_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must include timezone")
        return value


class ReferralDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    decision: Literal["accepted", "declined"]
    rationale: str = Field(min_length=5, max_length=2000)
    receiving_service: str | None = Field(default=None, max_length=160)
    planned_at: datetime | None = None

    @field_validator("planned_at")
    @classmethod
    def planned_at_aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("planned_at must include timezone")
        return value


class ReferralCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    outcome: Literal["completed", "patient_declined", "unable_to_contact", "cancelled"]
    summary: str = Field(min_length=5, max_length=4000)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def completed_at_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("completed_at must include timezone")
        return value


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, referral_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}", action=action,
        resource_type="referral", resource_id=referral_id, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id, **(metadata or {})},
        session=session,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_referral(payload: ReferralCreate, request: Request,
                          principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    REFERRAL_CREATE_ROLES)
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
    if payload.requested_at > now:
        raise HTTPException(status_code=422, detail="Referral request time cannot be in the future")
    referral_id = str(uuid4())
    record = payload.model_dump() | {
        "referral_id": referral_id, "status": "awaiting_receipt",
        "created_at": now, "created_by_issuer": principal.issuer,
        "created_by_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.referrals.insert_one(record, session=session)
            await _audit(db, session, principal, "referral.create", referral_id,
                         payload.tenant_id, payload.facility_id,
                         {"patient_id": payload.patient_id, "urgency": payload.urgency,
                          "referral_type": payload.referral_type})
    return {"referral_id": referral_id, "status": "awaiting_receipt", "created_at": now}


@router.post("/{referral_id}/decision")
async def decide_referral(referral_id: str, payload: ReferralDecision, request: Request,
                          principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    REFERRAL_RECEIVE_ROLES)
    now = datetime.now(timezone.utc)
    if payload.planned_at is not None and payload.planned_at < now:
        raise HTTPException(status_code=422, detail="Planned referral time must not be in the past")
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            referral = await db.referrals.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "referral_id": referral_id, "status": "awaiting_receipt",
            }, session=session)
            if referral is None:
                raise HTTPException(status_code=404, detail="Referral awaiting receipt not found")
            if referral["created_by_issuer"] == principal.issuer and referral["created_by_subject"] == principal.subject:
                raise HTTPException(status_code=403, detail="Referral author cannot record receiving decision")
            changed = await db.referrals.update_one(
                {"_id": referral["_id"], "status": "awaiting_receipt"},
                {"$set": {"status": payload.decision, "decision": payload.decision,
                          "decision_rationale": payload.rationale, "receiving_service": payload.receiving_service,
                          "planned_at": payload.planned_at, "decided_at": now,
                          "decided_by_issuer": principal.issuer, "decided_by_subject": principal.subject}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Referral state changed; reload before retrying")
            await _audit(db, session, principal, "referral.decision", referral_id,
                         payload.tenant_id, payload.facility_id, {"decision": payload.decision})
    return {"referral_id": referral_id, "status": payload.decision, "decided_at": now}


@router.post("/{referral_id}/complete")
async def complete_referral(referral_id: str, payload: ReferralCompletion, request: Request,
                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    REFERRAL_CREATE_ROLES)
    now = datetime.now(timezone.utc)
    if payload.completed_at > now:
        raise HTTPException(status_code=422, detail="Completion time cannot be in the future")
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            referral = await db.referrals.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "referral_id": referral_id, "status": "accepted",
            }, session=session)
            if referral is None:
                raise HTTPException(status_code=404, detail="Accepted referral not found")
            changed = await db.referrals.update_one(
                {"_id": referral["_id"], "status": "accepted"},
                {"$set": {"status": "closed", "outcome": payload.outcome,
                          "completion_summary": payload.summary, "completed_at": payload.completed_at,
                          "closed_at": now, "closed_by_issuer": principal.issuer,
                          "closed_by_subject": principal.subject}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Referral state changed; reload before retrying")
            await _audit(db, session, principal, "referral.complete", referral_id,
                         payload.tenant_id, payload.facility_id, {"outcome": payload.outcome})
    return {"referral_id": referral_id, "status": "closed", "outcome": payload.outcome}
