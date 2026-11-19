"""Facility-scoped chart of accounts and immutable double-entry journal foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/accounting", tags=["accounting"])
ADMIN_ROLES = ["facility_admin"]
POST_ROLES = ["facility_admin", "finance_officer"]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    account_code: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    account_type: Literal["asset", "liability", "equity", "revenue", "expense"]
    normal_balance: Literal["debit", "credit"]
    parent_account_code: str | None = Field(default=None, max_length=32)


class JournalLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_code: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=200)
    debit_minor: int = Field(default=0, ge=0, le=10**12)
    credit_minor: int = Field(default=0, ge=0, le=10**12)

    @model_validator(mode="after")
    def exactly_one_side(self):
        if (self.debit_minor > 0) == (self.credit_minor > 0):
            raise ValueError("Each journal line must have either a positive debit or a positive credit")
        return self


class JournalPost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    journal_date: datetime
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    description: str = Field(min_length=3, max_length=500)
    source_type: str = Field(min_length=2, max_length=64)
    source_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=128)
    lines: list[JournalLine] = Field(min_length=2, max_length=100)

    @model_validator(mode="after")
    def balanced_and_valid_date(self):
        if self.journal_date.tzinfo is None or self.journal_date.utcoffset() is None:
            raise ValueError("journal_date must include a timezone")
        debits = sum(line.debit_minor for line in self.lines)
        credits = sum(line.credit_minor for line in self.lines)
        if debits <= 0 or debits != credits or debits > 10**12:
            raise ValueError("Journal must balance to a positive total within supported limits")
        if len({line.account_code for line in self.lines}) != len(self.lines):
            raise ValueError("Each account may appear only once per journal")
        return self


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
async def create_account(payload: AccountCreate, request: Request,
                         principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ADMIN_ROLES)
    if payload.parent_account_code:
        parent = await db.chart_of_accounts.find_one({
            "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
            "account_code": payload.parent_account_code, "status": "active",
        }, projection={"_id": 1})
        if parent is None:
            raise HTTPException(status_code=422, detail="Parent account is not active in this facility")
    account_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "account_id": account_id, "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db.chart_of_accounts.insert_one(record, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="accounting.account.create", resource_type="account",
                    resource_id=account_id, tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id, "account_code": payload.account_code},
                    session=session,
                )
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="Account code already exists") from exc
        raise
    return {"account_id": account_id, "account_code": payload.account_code, "status": "active"}


@router.post("/journals", status_code=status.HTTP_201_CREATED)
async def post_journal(payload: JournalPost, request: Request,
                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, POST_ROLES)
    codes = [line.account_code for line in payload.lines]
    accounts = await db.chart_of_accounts.find({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "account_code": {"$in": codes}, "status": "active",
    }).to_list(length=len(codes))
    if len(accounts) != len(codes):
        raise HTTPException(status_code=422, detail="Every journal account must be active in this facility")
    journal_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "journal_id": journal_id, "status": "posted", "posted_at": now,
        "posted_by_issuer": principal.issuer, "posted_by_subject": principal.subject,
        "total_debit_minor": sum(line.debit_minor for line in payload.lines),
        "total_credit_minor": sum(line.credit_minor for line in payload.lines),
        "created_at": now,
    }
    client = request.app.state.mongo_client
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db.journal_entries.insert_one(record, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="accounting.journal.post", resource_type="journal",
                    resource_id=journal_id, tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id,
                              "currency": payload.currency, "total_minor": record["total_debit_minor"],
                              "source_type": payload.source_type, "source_id": payload.source_id},
                    session=session,
                )
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="Idempotency key already used") from exc
        raise
    return {"journal_id": journal_id, "status": "posted",
            "total_debit_minor": record["total_debit_minor"],
            "total_credit_minor": record["total_credit_minor"], "posted_at": now}
