"""Billing, receipts and cash-session foundation using integer minor units."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/finance", tags=["finance"])
FINANCE_ROLES = ["facility_admin", "finance_officer"]


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=2, max_length=200)
    quantity: int = Field(gt=0, le=100000)
    unit_amount_minor: int = Field(ge=0, le=10**12)


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str | None = Field(default=None, max_length=64)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    lines: list[InvoiceLine] = Field(min_length=1, max_length=100)


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    amount_minor: int = Field(gt=0, le=10**12)
    method: Literal["cash", "mobile_money", "card", "bank_transfer", "insurance", "other"]
    external_reference: str | None = Field(default=None, max_length=160)


class CashSessionOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    opening_float_minor: int = Field(ge=0, le=10**12)


class CashSessionClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    counted_cash_minor: int = Field(ge=0, le=10**12)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/invoices", status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: InvoiceCreate, request: Request,
                         principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, FINANCE_ROLES)
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    if patient is None:
        raise HTTPException(status_code=404, detail="Active patient not found")
    if payload.encounter_id and await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
    }, projection={"_id": 1}) is None:
        raise HTTPException(status_code=404, detail="Encounter not found for patient")
    total = sum(line.quantity * line.unit_amount_minor for line in payload.lines)
    if total > 10**12:
        raise HTTPException(status_code=422, detail="Invoice total exceeds supported limit")
    invoice_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "invoice_id": invoice_id, "total_minor": total, "paid_minor": 0,
        "balance_minor": total, "status": "issued", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.invoices.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="invoice.create", resource_type="invoice", resource_id=invoice_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "total_minor": total, "currency": payload.currency},
                session=session,
            )
    return {"invoice_id": invoice_id, "total_minor": total, "balance_minor": total,
            "currency": payload.currency, "status": "issued"}


@router.post("/invoices/{invoice_id}/payments", status_code=status.HTTP_201_CREATED)
async def receive_payment(invoice_id: str, payload: PaymentCreate, request: Request,
                          principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, FINANCE_ROLES)
    now, payment_id = datetime.now(timezone.utc), str(uuid4())
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            invoice = await db.invoices.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "invoice_id": invoice_id, "status": {"$in": ["issued", "partially_paid"]},
            }, session=session)
            if invoice is None:
                raise HTTPException(status_code=404, detail="Open invoice not found")
            if payload.amount_minor > invoice["balance_minor"]:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance")
            balance = invoice["balance_minor"] - payload.amount_minor
            paid = invoice["paid_minor"] + payload.amount_minor
            result = await db.invoices.update_one({
                "_id": invoice["_id"], "balance_minor": invoice["balance_minor"],
                "status": {"$in": ["issued", "partially_paid"]},
            }, {"$set": {
                "paid_minor": paid, "balance_minor": balance,
                "status": "paid" if balance == 0 else "partially_paid",
                "updated_at": now,
            }}, session=session)
            if result.modified_count != 1:
                raise HTTPException(status_code=409, detail="Invoice changed; retry payment")
            await db.payments.insert_one({
                "payment_id": payment_id, "invoice_id": invoice_id,
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "patient_id": invoice["patient_id"], "amount_minor": payload.amount_minor,
                "currency": invoice["currency"], "method": payload.method,
                "external_reference": payload.external_reference, "received_at": now,
                "received_by_issuer": principal.issuer, "received_by_subject": principal.subject,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="payment.receive", resource_type="payment", resource_id=payment_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "invoice_id": invoice_id,
                          "amount_minor": payload.amount_minor}, session=session,
            )
    return {"payment_id": payment_id, "invoice_id": invoice_id,
            "amount_minor": payload.amount_minor, "balance_minor": balance,
            "invoice_status": "paid" if balance == 0 else "partially_paid"}


@router.post("/cash-sessions/open", status_code=status.HTTP_201_CREATED)
async def open_cash_session(payload: CashSessionOpen, request: Request,
                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, FINANCE_ROLES)
    session_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "cash_session_id": session_id, "status": "open", "opened_at": now,
        "opening_by_issuer": principal.issuer, "opening_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            active = await db.cash_sessions.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "opened_by_subject": principal.subject, "status": "open",
            }, session=session)
            if active:
                raise HTTPException(status_code=409, detail="Cash session already open for this operator")
            await db.cash_sessions.insert_one(record | {
                "opened_by_subject": principal.subject,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="cash_session.open", resource_type="cash_session", resource_id=session_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id}, session=session,
            )
    return {"cash_session_id": session_id, "status": "open", "opened_at": now}


@router.post("/cash-sessions/{cash_session_id}/close")
async def close_cash_session(cash_session_id: str, payload: CashSessionClose, request: Request,
                             principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, FINANCE_ROLES)
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            cash = await db.cash_sessions.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "cash_session_id": cash_session_id, "status": "open",
                "opened_by_subject": principal.subject,
            }, session=session)
            if cash is None:
                raise HTTPException(status_code=404, detail="Open cash session not found for operator")
            expected = cash["opening_float_minor"] + await db.payments.aggregate([
                {"$match": {"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                            "received_by_subject": principal.subject, "method": "cash",
                            "received_at": {"$gte": cash["opened_at"]}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount_minor"}}},
            ], session=session).to_list(length=1)
            expected_cash = expected[0]["total"] + cash["opening_float_minor"] if expected else cash["opening_float_minor"]
            variance = payload.counted_cash_minor - expected_cash
            await db.cash_sessions.update_one(
                {"_id": cash["_id"], "status": "open"},
                {"$set": {"status": "closed", "closed_at": now,
                          "counted_cash_minor": payload.counted_cash_minor,
                          "expected_cash_minor": expected_cash, "variance_minor": variance}},
                session=session,
            )
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="cash_session.close", resource_type="cash_session",
                resource_id=cash_session_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "variance_minor": variance},
                session=session,
            )
    return {"cash_session_id": cash_session_id, "status": "closed",
            "expected_cash_minor": expected_cash, "counted_cash_minor": payload.counted_cash_minor,
            "variance_minor": variance, "closed_at": now}
