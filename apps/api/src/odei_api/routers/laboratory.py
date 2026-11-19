"""Laboratory order, specimen and result lifecycle foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/laboratory", tags=["laboratory"])
ORDER_ROLES = ["facility_admin", "clinician"]
SPECIMEN_ROLES = ["facility_admin", "nurse", "lab_scientist"]
RESULT_ROLES = ["facility_admin", "lab_scientist"]


class LabOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    tests: list[str] = Field(min_length=1, max_length=40)
    clinical_indication: str | None = Field(default=None, max_length=2000)
    priority: Literal["routine", "urgent", "stat"] = "routine"


class SpecimenCollect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    specimen_type: str = Field(min_length=2, max_length=100)
    container: str | None = Field(default=None, max_length=100)
    collection_site: str | None = Field(default=None, max_length=200)


class LabResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    analyte_code: str = Field(min_length=1, max_length=80)
    analyte_name: str = Field(min_length=2, max_length=160)
    value: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, max_length=40)
    reference_range: str | None = Field(default=None, max_length=100)
    interpretation: Literal["normal", "low", "high", "critical", "indeterminate", "not_interpreted"] = "not_interpreted"
    comment: str | None = Field(default=None, max_length=2000)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, resource_type, resource_id, tenant_id, facility_id):
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}", action=action,
        resource_type=resource_type, resource_id=resource_id, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id}, session=session,
    )


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_lab_order(
    payload: LabOrderCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ORDER_ROLES)
    patient = await db.patients.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active",
    }, projection={"_id": 1})
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "encounter_id": payload.encounter_id, "status": "open",
    }, projection={"_id": 1})
    if patient is None or encounter is None:
        raise HTTPException(status_code=404, detail="Active patient or open encounter not found")
    order_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "order_id": order_id, "status": "awaiting_specimen",
        "created_at": now, "ordered_by_issuer": principal.issuer,
        "ordered_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.lab_orders.insert_one(record, session=session)
            await _audit(db, session, principal, "lab_order.create", "lab_order", order_id,
                         payload.tenant_id, payload.facility_id)
    return {"order_id": order_id, "status": "awaiting_specimen", "created_at": now}


@router.post("/orders/{order_id}/specimens", status_code=status.HTTP_201_CREATED)
async def collect_specimen(
    order_id: str, payload: SpecimenCollect, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, SPECIMEN_ROLES)
    order = await db.lab_orders.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "order_id": order_id, "status": "awaiting_specimen",
    }, projection={"_id": 1})
    if order is None:
        raise HTTPException(status_code=404, detail="Order awaiting specimen not found")
    specimen_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "specimen_id": specimen_id, "order_id": order_id,
        "status": "collected", "collected_at": now,
        "collector_issuer": principal.issuer, "collector_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.specimens.insert_one(record | {
                "patient_id": (await db.lab_orders.find_one({"_id": order["_id"]}, session=session))["patient_id"],
            }, session=session)
            changed = await db.lab_orders.update_one(
                {"_id": order["_id"], "status": "awaiting_specimen"},
                {"$set": {"status": "specimen_collected", "specimen_id": specimen_id}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Order state changed; retry")
            await _audit(db, session, principal, "specimen.collect", "specimen", specimen_id,
                         payload.tenant_id, payload.facility_id)
    return {"specimen_id": specimen_id, "order_id": order_id, "status": "collected", "collected_at": now}


@router.post("/orders/{order_id}/results", status_code=status.HTTP_201_CREATED)
async def record_lab_result(
    order_id: str, payload: LabResultCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, RESULT_ROLES)
    order = await db.lab_orders.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "order_id": order_id, "status": "specimen_collected",
    })
    if order is None:
        raise HTTPException(status_code=404, detail="Order with collected specimen not found")
    result_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "result_id": result_id, "order_id": order_id,
        "specimen_id": order["specimen_id"], "patient_id": order["patient_id"],
        "status": "preliminary", "recorded_at": now,
        "recorder_issuer": principal.issuer, "recorder_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            changed = await db.lab_orders.update_one(
                {"_id": order["_id"], "status": "specimen_collected"},
                {"$set": {"status": "result_preliminary", "latest_result_id": result_id}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Order state changed; retry result recording")
            await db.lab_results.insert_one(record, session=session)
            await _audit(db, session, principal, "lab_result.record", "lab_result", result_id,
                         payload.tenant_id, payload.facility_id)
    return {"result_id": result_id, "order_id": order_id, "status": "preliminary", "recorded_at": now}
