"""Secure offline device enrollment and staged synchronization intake.

Incoming offline changes are evidence, not trusted commands. They are stored
in a facility-scoped inbox for explicit reconciliation; this API never applies
client payloads directly to clinical, stock or financial records.
"""
import base64
import binascii
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/sync", tags=["offline-synchronization"])
DEVICE_ROLES = ["facility_admin", "medical_records_officer", "clinician", "nurse", "pharmacist", "lab_scientist"]


class DeviceEnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    device_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    public_key_pem: str = Field(min_length=80, max_length=2000)
    label: str = Field(min_length=2, max_length=100)

    @field_validator("public_key_pem")
    @classmethod
    def validate_ed25519_key(cls, value):
        try:
            key = serialization.load_pem_public_key(value.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise ValueError("A valid PEM public key is required") from exc
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("Only Ed25519 device keys are supported")
        return value


class OfflineChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    aggregate_type: str = Field(min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    aggregate_id: str = Field(min_length=1, max_length=100)
    base_version: int = Field(ge=0)
    client_recorded_at: datetime
    change_type: str = Field(min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    payload: dict = Field(max_length=100)

    @field_validator("client_recorded_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("client_recorded_at must include a timezone")
        return value

    @model_validator(mode="after")
    def bound_payload_size(self):
        encoded = json.dumps(self.payload, sort_keys=True, separators=(",", ":"), default=str)
        if len(encoded.encode("utf-8")) > 32768:
            raise ValueError("Each offline payload is limited to 32 KiB")
        return self


class SyncBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    device_id: str = Field(min_length=8, max_length=100)
    batch_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    changes: list[OfflineChange] = Field(min_length=1, max_length=100)
    signature: str = Field(min_length=80, max_length=256)

    @model_validator(mode="after")
    def unique_change_ids(self):
        ids = [change.change_id for change in self.changes]
        if len(set(ids)) != len(ids):
            raise ValueError("change_id values must be unique within a batch")
        return self


class SyncReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    decision: str = Field(pattern=r"^(accepted_for_manual_reconciliation|rejected)$")
    rationale: str = Field(min_length=10, max_length=1000)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


def _canonical_batch(values: dict) -> bytes:
    signed = dict(values)
    signed["changes"] = [
        change.model_dump(mode="json") if isinstance(change, OfflineChange) else change
        for change in signed["changes"]
    ]
    return json.dumps(
        signed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _signed_bytes(payload: SyncBatchCreate) -> bytes:
    return _canonical_batch({
        "tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id,
        "device_id": payload.device_id,
        "batch_id": payload.batch_id,
        "changes": payload.changes,
    })


@router.post("/devices", status_code=status.HTTP_201_CREATED)
async def enroll_device(
    payload: DeviceEnrollmentCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ["facility_admin"])
    existing = await db.sync_devices.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "device_id": payload.device_id,
    })
    if existing:
        raise HTTPException(status_code=409, detail="Device identifier already enrolled; use a controlled key-rotation workflow")
    now = datetime.now(timezone.utc)
    record = {
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "device_id": payload.device_id, "public_key_pem": payload.public_key_pem,
        "label": payload.label, "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
        "last_seen_at": None,
    }
    await db.sync_devices.insert_one(record)
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}",
        action="sync.device.enroll", resource_type="sync_device",
        resource_id=payload.device_id, tenant_id=payload.tenant_id,
        outcome="success", metadata={"facility_id": payload.facility_id, "label": payload.label},
    )
    return {"device_id": payload.device_id, "status": "active", "signature_algorithm": "Ed25519"}


@router.post("/batches", status_code=status.HTTP_202_ACCEPTED)
async def receive_sync_batch(
    payload: SyncBatchCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, DEVICE_ROLES
    )
    device = await db.sync_devices.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "device_id": payload.device_id, "status": "active",
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    })
    if device is None:
        raise HTTPException(status_code=403, detail="No active device enrolled to this authenticated user and facility")
    try:
        public_key = serialization.load_pem_public_key(device["public_key_pem"].encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            raise ValueError("Unsupported key")
        signature = base64.b64decode(payload.signature, validate=True)
        public_key.verify(signature, _signed_bytes(payload))
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise HTTPException(status_code=401, detail="Offline batch signature verification failed") from exc

    now = datetime.now(timezone.utc)
    batch_record = {
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "device_id": payload.device_id, "batch_id": payload.batch_id,
        "change_ids": [change.change_id for change in payload.changes],
        "received_at": now, "received_by_issuer": principal.issuer,
        "received_by_subject": principal.subject, "status": "received",
    }
    staged = [{
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "device_id": payload.device_id, "batch_id": payload.batch_id,
        "change_id": change.change_id, "aggregate_type": change.aggregate_type,
        "aggregate_id": change.aggregate_id, "base_version": change.base_version,
        "client_recorded_at": change.client_recorded_at,
        "change_type": change.change_type, "payload": change.payload,
        "received_at": now, "received_by_issuer": principal.issuer,
        "received_by_subject": principal.subject, "status": "pending_review",
    } for change in payload.changes]
    try:
        async with await request.app.state.mongo_client.start_session() as session:
            async with session.start_transaction():
                await db.sync_batches.insert_one(batch_record, session=session)
                await db.sync_inbox.insert_many(staged, ordered=True, session=session)
                await db.sync_devices.update_one(
                    {"_id": device["_id"], "status": "active"},
                    {"$set": {"last_seen_at": now}}, session=session,
                )
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="sync.batch.receive", resource_type="sync_batch",
                    resource_id=payload.batch_id, tenant_id=payload.tenant_id,
                    outcome="success",
                    metadata={"facility_id": payload.facility_id, "device_id": payload.device_id,
                              "change_count": len(staged), "signature_algorithm": "Ed25519"},
                    session=session,
                )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Batch or change already received; retry using the original batch identifier") from exc
    return {"batch_id": payload.batch_id, "accepted_count": len(staged),
            "status": "pending_review", "applied_count": 0}


@router.get("/inbox")
async def list_sync_inbox(
    tenant_id: str, facility_id: str, request: Request,
    limit: int = 50, principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, tenant_id, facility_id,
        ["facility_admin", "medical_records_officer", "privacy_officer", "data_protection_officer"],
    )
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    items = await db.sync_inbox.find({
        "tenant_id": tenant_id, "facility_id": facility_id, "status": "pending_review",
    }, projection={"_id": 0, "payload": 0}).sort(
        [("received_at", 1)]
    ).limit(limit).to_list(length=limit)
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}",
        action="sync.inbox.read", resource_type="sync_inbox",
        resource_id=facility_id, tenant_id=tenant_id, outcome="success",
        metadata={"returned_count": len(items)},
    )
    return {"items": items, "limit": limit, "truncated_possible": len(items) == limit}


@router.post("/inbox/{change_id}/review")
async def review_sync_change(
    change_id: str, payload: SyncReviewCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id,
        ["facility_admin", "medical_records_officer", "privacy_officer", "data_protection_officer"],
    )
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            change = await db.sync_inbox.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "change_id": change_id, "status": "pending_review",
            }, session=session)
            if change is None:
                raise HTTPException(status_code=404, detail="Pending synchronization change not found")
            new_status = payload.decision
            result = await db.sync_inbox.update_one(
                {"_id": change["_id"], "status": "pending_review"},
                {"$set": {"status": new_status, "reviewed_at": now,
                          "reviewed_by_issuer": principal.issuer,
                          "reviewed_by_subject": principal.subject,
                          "review_rationale": payload.rationale}}, session=session,
            )
            if result.modified_count != 1:
                raise HTTPException(status_code=409, detail="Synchronization change was already reviewed")
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="sync.change.review", resource_type="sync_change",
                resource_id=change_id, tenant_id=payload.tenant_id,
                outcome="success",
                metadata={"facility_id": payload.facility_id, "decision": new_status,
                          "aggregate_type": change["aggregate_type"]},
                session=session,
            )
    return {"change_id": change_id, "status": new_status, "applied": False}
