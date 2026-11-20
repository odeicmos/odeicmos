"""Payer, eligibility evidence and insurance-claim workflow foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/insurance", tags=["insurance"])
CLAIMS_ROLES = ["facility_admin", "claims_officer"]
PAYER_ROLES = ["facility_admin"]


class PayerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    payer_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=200)
    contact_reference: str | None = Field(default=None, max_length=200)


class EligibilityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    payer_code: str = Field(min_length=1, max_length=64)
    member_number: str = Field(min_length=1, max_length=120)
    policy_number: str | None = Field(default=None, max_length=120)
    coverage_status: Literal["eligible", "ineligible", "pending", "unknown"]
    checked_at: datetime
    valid_until: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=300)


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    invoice_id: str = Field(min_length=1, max_length=64)
    eligibility_id: str = Field(min_length=1, max_length=64)
    claimed_amount_minor: int = Field(gt=0, le=10**12)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")


class ClaimDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    decision: Literal["accepted", "partially_accepted", "rejected"]
    approved_amount_minor: int = Field(ge=0, le=10**12)
    payer_reference: str | None = Field(default=None, max_length=160)
    reason: str = Field(min_length=3, max_length=2000)



class ClaimAppeal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=10, max_length=3000)
    evidence_reference: str | None = Field(default=None, max_length=300)

def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, kind, rid, tenant_id, facility_id, metadata=None):
    await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
        action=action, resource_type=kind, resource_id=rid, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id, **(metadata or {})}, session=session)


@router.post("/payers", status_code=status.HTTP_201_CREATED)
async def create_payer(payload: PayerCreate, request: Request,
                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, PAYER_ROLES)
    payer_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {"payer_id": payer_id, "status": "active", "created_at": now}
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            if await db.payers.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "payer_code": payload.payer_code}, session=session):
                raise HTTPException(status_code=409, detail="Payer code already exists")
            await db.payers.insert_one(record, session=session)
            await _audit(db, session, principal, "payer.create", "payer", payer_id,
                         payload.tenant_id, payload.facility_id)
    return {"payer_id": payer_id, "payer_code": payload.payer_code, "status": "active"}


@router.post("/eligibility", status_code=status.HTTP_201_CREATED)
async def record_eligibility(payload: EligibilityRecord, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CLAIMS_ROLES)
    payer = await db.payers.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "payer_code": payload.payer_code, "status": "active"})
    patient = await db.patients.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "patient_id": payload.patient_id, "record_status": "active"})
    if payer is None or patient is None:
        raise HTTPException(status_code=404, detail="Active payer and patient are required")
    if payload.checked_at.tzinfo is None or payload.checked_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="checked_at must include timezone")
    if payload.checked_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="checked_at cannot be in the future")
    if payload.valid_until and (payload.valid_until.tzinfo is None or payload.valid_until.utcoffset() is None):
        raise HTTPException(status_code=422, detail="valid_until must include timezone")
    eligibility_id, now = str(uuid4()), datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.insurance_eligibility.insert_one(payload.model_dump() | {
                "eligibility_id": eligibility_id, "recorded_at": now,
                "recorded_by_subject": principal.subject}, session=session)
            await _audit(db, session, principal, "insurance.eligibility.record",
                "insurance_eligibility", eligibility_id, payload.tenant_id, payload.facility_id)
    return {"eligibility_id": eligibility_id, "coverage_status": payload.coverage_status}


@router.post("/claims", status_code=status.HTTP_201_CREATED)
async def create_claim(payload: ClaimCreate, request: Request,
                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CLAIMS_ROLES)
    invoice = await db.invoices.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "invoice_id": payload.invoice_id})
    eligibility = await db.insurance_eligibility.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "eligibility_id": payload.eligibility_id,
        "coverage_status": "eligible"})
    if invoice is None or eligibility is None:
        raise HTTPException(status_code=404, detail="Invoice or eligible coverage evidence not found")
    payer = await db.payers.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "payer_code": eligibility["payer_code"], "status": "active"})
    if payer is None:
        raise HTTPException(status_code=409, detail="Payer is inactive or no longer configured")
    if invoice.get("status") not in ["issued", "partially_paid"] or invoice["currency"] != payload.currency or payload.claimed_amount_minor > invoice["balance_minor"]:
        raise HTTPException(status_code=409, detail="Claim requires an open invoice and amount within its outstanding balance")
    now = datetime.now(timezone.utc)
    if eligibility["patient_id"] != invoice["patient_id"]:
        raise HTTPException(status_code=409, detail="Coverage evidence belongs to a different patient")
    if eligibility["checked_at"] > now or (eligibility.get("valid_until") and eligibility["valid_until"] < now):
        raise HTTPException(status_code=409, detail="Eligibility evidence is outside its valid time window")
    claim_id = str(uuid4())
    record = payload.model_dump() | {"claim_id": claim_id, "patient_id": invoice["patient_id"],
        "payer_code": eligibility["payer_code"], "status": "submitted",
        "submitted_at": now, "submitted_by_subject": principal.subject}
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.insurance_claims.insert_one(record, session=session)
            await _audit(db, session, principal, "insurance.claim.submit", "insurance_claim",
                claim_id, payload.tenant_id, payload.facility_id,
                {"invoice_id": payload.invoice_id, "claimed_amount_minor": payload.claimed_amount_minor})
    return {"claim_id": claim_id, "status": "submitted", "submitted_at": now}


@router.post("/claims/{claim_id}/decision")
async def decide_claim(claim_id: str, payload: ClaimDecision, request: Request,
                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CLAIMS_ROLES)
    claim = await db.insurance_claims.find_one({"tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id, "claim_id": claim_id, "status": "submitted"})
    if claim is None:
        raise HTTPException(status_code=404, detail="Submitted claim not found")
    if payload.approved_amount_minor > claim["claimed_amount_minor"]:
        raise HTTPException(status_code=422, detail="Approved amount exceeds claimed amount")
    if payload.decision == "accepted" and payload.approved_amount_minor != claim["claimed_amount_minor"]:
        raise HTTPException(status_code=422, detail="Accepted claim must approve the full claimed amount")
    if payload.decision == "rejected" and payload.approved_amount_minor != 0:
        raise HTTPException(status_code=422, detail="Rejected claim must approve zero")
    if payload.decision == "partially_accepted" and not 0 < payload.approved_amount_minor < claim["claimed_amount_minor"]:
        raise HTTPException(status_code=422, detail="Partially accepted claim must approve a positive amount below the claim")
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            changed = await db.insurance_claims.update_one({"_id": claim["_id"], "status": "submitted"},
                {"$set": {"status": payload.decision, "approved_amount_minor": payload.approved_amount_minor,
                          "payer_reference": payload.payer_reference, "decision_reason": payload.reason,
                          "decided_at": now, "decided_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Claim state changed; retry")
            await _audit(db, session, principal, "insurance.claim.decide", "insurance_claim",
                claim_id, payload.tenant_id, payload.facility_id,
                {"decision": payload.decision, "approved_amount_minor": payload.approved_amount_minor})
    return {"claim_id": claim_id, "status": payload.decision,
            "approved_amount_minor": payload.approved_amount_minor, "decided_at": now}

@router.post("/claims/{claim_id}/appeals", status_code=status.HTTP_201_CREATED)
async def appeal_claim(claim_id: str, payload: ClaimAppeal, request: Request,
                      principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, CLAIMS_ROLES)
    now, appeal_id = datetime.now(timezone.utc), str(uuid4())
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            claim = await db.insurance_claims.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "claim_id": claim_id, "status": {"$in": ["rejected", "partially_accepted"]},
            }, session=session)
            if claim is None:
                raise HTTPException(status_code=404, detail="Rejected or partially accepted claim not found")
            prior = await db.insurance_claim_appeals.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "claim_id": claim_id, "status": "submitted",
            }, session=session)
            if prior:
                raise HTTPException(status_code=409, detail="An appeal is already awaiting review")
            await db.insurance_claim_appeals.insert_one(payload.model_dump() | {
                "appeal_id": appeal_id, "claim_id": claim_id, "invoice_id": claim["invoice_id"],
                "status": "submitted", "submitted_at": now,
                "submitted_by_issuer": principal.issuer, "submitted_by_subject": principal.subject,
            }, session=session)
            await _audit(db, session, principal, "insurance.claim.appeal", "insurance_claim_appeal",
                appeal_id, payload.tenant_id, payload.facility_id, {"claim_id": claim_id})
    return {"appeal_id": appeal_id, "claim_id": claim_id, "status": "submitted", "submitted_at": now}
