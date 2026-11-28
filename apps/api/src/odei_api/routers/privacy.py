"""Patient privacy notice, lawful-basis and consent event APIs.

Events are append-only. A withdrawal is a new event, never an edit to the
original grant. This initial service is not a legal-basis determination engine.
"""
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/privacy", tags=["privacy-and-consent"])
PRIVACY_ROLES = [
    "facility_admin", "clinician", "nurse", "medical_records_officer",
    "privacy_officer", "data_protection_officer",
]


class ConsentEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    purpose_code: str = Field(min_length=2, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")
    data_categories: list[str] = Field(min_length=1, max_length=30)
    action: Literal["granted", "declined", "withdrawn", "basis_recorded"]
    lawful_basis: Literal[
        "consent", "healthcare_delivery", "legal_obligation",
        "public_health", "vital_interests", "other_authorized_basis",
    ]
    notice_version: str = Field(min_length=1, max_length=40)
    recorded_at: datetime
    expires_at: datetime | None = None
    evidence_reference: str | None = Field(default=None, min_length=3, max_length=500)
    representative_name: str | None = Field(default=None, max_length=200)
    representative_relationship: str | None = Field(default=None, max_length=100)
    rationale: str | None = Field(default=None, max_length=1000)

    @field_validator("recorded_at", "expires_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must include a timezone")
        return value

    @field_validator("data_categories")
    @classmethod
    def normalize_categories(cls, values):
        normalized = [value.strip().lower() for value in values]
        if any(not value or len(value) > 80 for value in normalized):
            raise ValueError("data categories must be non-empty and at most 80 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("data categories must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_basis_action(self):
        if self.action in ["granted", "declined", "withdrawn"] and self.lawful_basis != "consent":
            raise ValueError("consent decisions must use the consent lawful basis")
        if self.action == "basis_recorded" and self.lawful_basis == "consent":
            raise ValueError("use a consent decision for the consent lawful basis")
        return self


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


def _consent_event_is_chronological(latest_event: dict | None, recorded_at: datetime) -> bool:
    """A new consent event must not be timestamped before the latest recorded event."""
    return latest_event is not None and recorded_at >= latest_event["recorded_at"]


@router.post("/consent-events", status_code=status.HTTP_201_CREATED)
async def record_consent_event(
    payload: ConsentEventCreate,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, PRIVACY_ROLES
    )
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Active patient not found in this facility")

    now = datetime.now(timezone.utc)
    if payload.recorded_at > now:
        raise HTTPException(status_code=422, detail="recorded_at cannot be in the future")
    if payload.expires_at is not None and payload.expires_at <= payload.recorded_at:
        raise HTTPException(status_code=422, detail="expires_at must be after recorded_at")
    if payload.action in ["granted", "declined", "withdrawn"] and payload.lawful_basis != "consent":
        raise HTTPException(status_code=422, detail="Consent decisions must use the consent lawful basis")
    if payload.action == "basis_recorded" and payload.lawful_basis == "consent":
        raise HTTPException(status_code=422, detail="Use a consent decision for the consent lawful basis")
    latest = await db.patient_consent_events.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "purpose_code": payload.purpose_code,
    }, sort=[("recorded_at", -1), ("created_at", -1)])
    if latest is not None and not _consent_event_is_chronological(latest, payload.recorded_at):
        raise HTTPException(status_code=422, detail="Consent event timestamp cannot predate the latest event")

    if payload.action == "withdrawn":
        categories_match = latest is not None and set(latest.get("data_categories", [])) == set(payload.data_categories)
        grant_unexpired = latest is not None and (
            latest.get("expires_at") is None or latest["expires_at"] > now
        )
        if (not categories_match or latest.get("action") != "granted"
                or latest.get("lawful_basis") != "consent" or not grant_unexpired):
            raise HTTPException(status_code=409, detail="No active matching consent grant can be withdrawn")

    event_id = str(uuid4())
    record = payload.model_dump() | {
        "event_id": event_id, "created_at": now,
        "actor_issuer": principal.issuer, "actor_subject": principal.subject,
    }
    try:
        async with await request.app.state.mongo_client.start_session() as session:
            async with session.start_transaction():
                await db.patient_consent_events.insert_one(record, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action=f"privacy.consent.{payload.action}",
                    resource_type="patient_consent_event", resource_id=event_id,
                    tenant_id=payload.tenant_id, outcome="success",
                    metadata={
                        "facility_id": payload.facility_id, "patient_id": payload.patient_id,
                        "purpose_code": payload.purpose_code,
                        "lawful_basis": payload.lawful_basis,
                    }, session=session,
                )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Consent event identifier conflict") from exc
    return {"event_id": event_id, "action": payload.action, "recorded_at": payload.recorded_at,
            "append_only": True}


class DataSubjectRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    request_type: Literal["access", "correction", "portability", "restriction", "erasure", "objection"]
    requester_type: Literal["patient", "authorized_representative"]
    requester_name: str = Field(min_length=2, max_length=200)
    requested_scope: str = Field(min_length=5, max_length=2000)
    received_at: datetime
    evidence_reference: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("received_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must include a timezone")
        return value


class IdentityVerificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    outcome: Literal["verified", "rejected"]
    method: Literal["in_person_document", "approved_remote_check", "representative_authority_check", "other_approved"]
    evidence_reference: str = Field(min_length=3, max_length=500)
    rationale: str = Field(min_length=10, max_length=1000)


class DataSubjectRequestTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    status: Literal["in_review", "fulfilled", "partially_fulfilled", "declined", "withdrawn"]
    rationale: str = Field(min_length=10, max_length=2000)
    evidence_reference: str | None = Field(default=None, min_length=3, max_length=500)


@router.post("/data-subject-requests", status_code=status.HTTP_201_CREATED)
async def create_data_subject_request(
    payload: DataSubjectRequestCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["facility_admin", "medical_records_officer", "privacy_officer", "data_protection_officer"],
    )
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id,
    }, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient record not found in this facility")
    now = datetime.now(timezone.utc)
    if payload.received_at > now:
        raise HTTPException(status_code=422, detail="received_at cannot be in the future")
    request_id = str(uuid4())
    record = payload.model_dump() | {
        "request_id": request_id, "status": "identity_verification_pending",
        "identity_status": "pending", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.data_subject_requests.insert_one(record, session=session)
            await db.data_subject_request_events.insert_one({
                "event_id": str(uuid4()), "request_id": request_id,
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "event_type": "request_received", "status": record["status"],
                "rationale": "Request registered; identity verification is pending.",
                "actor_issuer": principal.issuer, "actor_subject": principal.subject,
                "occurred_at": now,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="privacy.data_subject_request.create",
                resource_type="data_subject_request", resource_id=request_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "request_type": payload.request_type},
                session=session,
            )
    return {"request_id": request_id, "status": record["status"], "identity_status": "pending"}


@router.post("/data-subject-requests/{request_id}/verify-identity")
async def verify_data_subject_request_identity(
    request_id: str, payload: IdentityVerificationCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["privacy_officer", "data_protection_officer"],
    )
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            case = await db.data_subject_requests.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "request_id": request_id, "identity_status": "pending",
            }, session=session)
            if case is None:
                raise HTTPException(status_code=404, detail="Request awaiting identity verification not found")
            new_status = "received" if payload.outcome == "verified" else "identity_verification_rejected"
            changed = await db.data_subject_requests.update_one(
                {"_id": case["_id"], "identity_status": "pending"},
                {"$set": {"identity_status": payload.outcome, "status": new_status,
                          "identity_verified_at": now, "identity_verified_by_issuer": principal.issuer,
                          "identity_verified_by_subject": principal.subject,
                          "identity_method": payload.method, "identity_evidence_reference": payload.evidence_reference,
                          "identity_rationale": payload.rationale}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Identity verification conflict")
            await db.data_subject_request_events.insert_one({
                "event_id": str(uuid4()), "request_id": request_id,
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "event_type": "identity_verification", "status": new_status,
                "rationale": payload.rationale, "evidence_reference": payload.evidence_reference,
                "actor_issuer": principal.issuer, "actor_subject": principal.subject,
                "occurred_at": now,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="privacy.data_subject_request.verify_identity",
                resource_type="data_subject_request", resource_id=request_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "outcome": payload.outcome},
                session=session,
            )
    return {"request_id": request_id, "status": new_status, "identity_status": payload.outcome}


@router.post("/data-subject-requests/{request_id}/transition")
async def transition_data_subject_request(
    request_id: str, payload: DataSubjectRequestTransition, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["privacy_officer", "data_protection_officer"],
    )
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            case = await db.data_subject_requests.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "request_id": request_id,
            }, session=session)
            if case is None:
                raise HTTPException(status_code=404, detail="Data subject request not found")
            current = case["status"]
            allowed = {
                "received": {"in_review", "declined", "withdrawn"},
                "in_review": {"fulfilled", "partially_fulfilled", "declined", "withdrawn"},
                "identity_verification_rejected": {"withdrawn"},
            }
            if payload.status not in allowed.get(current, set()):
                raise HTTPException(status_code=409, detail="Invalid data subject request transition")
            if payload.status == "in_review" and case.get("identity_status") != "verified":
                raise HTTPException(status_code=403, detail="Verified requester identity is required before review")
            changed = await db.data_subject_requests.update_one(
                {"_id": case["_id"], "status": current},
                {"$set": {"status": payload.status, "updated_at": now,
                          "last_action_by_issuer": principal.issuer,
                          "last_action_by_subject": principal.subject,
                          "last_action_rationale": payload.rationale,
                          "last_action_evidence_reference": payload.evidence_reference}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Request changed; reload before transition")
            await db.data_subject_request_events.insert_one({
                "event_id": str(uuid4()), "request_id": request_id,
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "event_type": "status_transition", "previous_status": current,
                "status": payload.status, "rationale": payload.rationale,
                "evidence_reference": payload.evidence_reference,
                "actor_issuer": principal.issuer, "actor_subject": principal.subject,
                "occurred_at": now,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="privacy.data_subject_request.transition",
                resource_type="data_subject_request", resource_id=request_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "from": current, "to": payload.status},
                session=session,
            )
    return {"request_id": request_id, "status": payload.status, "updated_at": now}


@router.get("/patients/{patient_id}/consent-events")
async def list_patient_consent_events(
    patient_id: str, tenant_id: str, facility_id: str, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, tenant_id, facility_id, PRIVACY_ROLES
    )
    events = await db.patient_consent_events.find({
        "tenant_id": tenant_id, "facility_id": facility_id, "patient_id": patient_id,
    }, projection={"_id": 0}).sort(
        [("recorded_at", -1), ("created_at", -1)]
    ).limit(100).to_list(length=100)
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}",
        action="privacy.consent.read", resource_type="patient_consent_events",
        resource_id=patient_id, tenant_id=tenant_id, outcome="success",
        metadata={"facility_id": facility_id, "returned_count": len(events)},
    )
    return {"events": events, "limit": 100, "truncated_possible": len(events) == 100}
