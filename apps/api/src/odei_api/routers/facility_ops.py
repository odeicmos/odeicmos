"""Facility asset register and controlled maintenance workflow."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/facility-operations", tags=["facility-operations"])
ADMIN_ROLES = ["facility_admin"]
MAINTENANCE_ROLES = ["facility_admin", "maintenance_officer", "clinical_engineer"]
RELEASE_ROLES = ["facility_admin", "clinical_engineer"]

class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    asset_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=2, max_length=160)
    category: Literal["medical_device", "building", "vehicle", "IT", "furniture", "other"]
    location_code: str = Field(min_length=1, max_length=80)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    risk_class: Literal["low", "medium", "high", "critical"]
    requires_calibration: bool = False

class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    asset_id: str = Field(min_length=1, max_length=64)
    issue_summary: str = Field(min_length=5, max_length=500)
    priority: Literal["routine", "urgent", "critical"]
    service_impact: Literal["none", "limited", "out_of_service"]
    evidence_reference: str | None = Field(default=None, max_length=300)

class WorkOrderAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    assignee_subject: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=5, max_length=1000)

class WorkOrderCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    work_performed: str = Field(min_length=10, max_length=3000)
    parts_reference: str | None = Field(default=None, max_length=300)
    calibration_evidence_reference: str | None = Field(default=None, max_length=300)

class AssetRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    release_checklist_reference: str = Field(min_length=8, max_length=300)
    rationale: str = Field(min_length=10, max_length=1000)

def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db

@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def create_asset(payload: AssetCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ADMIN_ROLES)
    asset_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {"asset_id": asset_id, "status": "in_service", "created_at": now,
        "created_by_subject": principal.subject}
    try:
        async with await request.app.state.mongo_client.start_session() as session:
            async with session.start_transaction():
                await db.facility_assets.insert_one(record, session=session)
                await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="facility.asset.create", resource_type="facility_asset", resource_id=asset_id,
                    tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id, "asset_code": payload.asset_code}, session=session)
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="Asset code already exists") from exc
        raise
    return {"asset_id": asset_id, "asset_code": payload.asset_code, "status": "in_service"}

@router.post("/work-orders", status_code=status.HTTP_201_CREATED)
async def create_work_order(payload: WorkOrderCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, MAINTENANCE_ROLES)
    now, work_order_id = datetime.now(timezone.utc), str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            asset = await db.facility_assets.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "asset_id": payload.asset_id, "status": {"$in": ["in_service", "maintenance"]}}, session=session)
            if asset is None:
                raise HTTPException(status_code=404, detail="Serviceable facility asset not found")
            if payload.priority == "critical" and payload.service_impact == "none":
                raise HTTPException(status_code=422, detail="Critical work order must record a service impact")
            await db.facility_work_orders.insert_one(payload.model_dump() | {"work_order_id": work_order_id,
                "asset_code": asset["asset_code"], "status": "open", "created_at": now,
                "created_by_subject": principal.subject}, session=session)
            if payload.service_impact != "none":
                changed = await db.facility_assets.update_one({"_id": asset["_id"], "status": asset["status"]},
                    {"$set": {"status": "maintenance", "updated_at": now}}, session=session)
                if changed.modified_count != 1:
                    raise HTTPException(status_code=409, detail="Asset state changed; retry work order")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="facility.work_order.create", resource_type="facility_work_order", resource_id=work_order_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "asset_id": payload.asset_id,
                          "priority": payload.priority, "service_impact": payload.service_impact}, session=session)
    return {"work_order_id": work_order_id, "status": "open", "created_at": now}

@router.post("/work-orders/{work_order_id}/assign")
async def assign_work_order(work_order_id: str, payload: WorkOrderAssignment, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, MAINTENANCE_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            order = await db.facility_work_orders.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "work_order_id": work_order_id, "status": "open"}, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Open work order not found")
            changed = await db.facility_work_orders.update_one({"_id": order["_id"], "status": "open"},
                {"$set": {"status": "assigned", "assignee_subject": payload.assignee_subject,
                    "assignment_reason": payload.reason, "assigned_at": now,
                    "assigned_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Work order state changed; retry")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="facility.work_order.assign", resource_type="facility_work_order", resource_id=work_order_id,
                tenant_id=payload.tenant_id, outcome="success", metadata={"facility_id": payload.facility_id}, session=session)
    return {"work_order_id": work_order_id, "status": "assigned", "assigned_at": now}

@router.post("/work-orders/{work_order_id}/complete")
async def complete_work_order(work_order_id: str, payload: WorkOrderCompletion, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, MAINTENANCE_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            order = await db.facility_work_orders.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "work_order_id": work_order_id, "status": "assigned", "assignee_subject": principal.subject}, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Assigned work order for this technician not found")
            changed = await db.facility_work_orders.update_one({"_id": order["_id"], "status": "assigned"},
                {"$set": {"status": "completed_pending_release", "work_performed": payload.work_performed,
                    "parts_reference": payload.parts_reference, "calibration_evidence_reference": payload.calibration_evidence_reference,
                    "completed_at": now, "completed_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Work order state changed; retry")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="facility.work_order.complete", resource_type="facility_work_order", resource_id=work_order_id,
                tenant_id=payload.tenant_id, outcome="success", metadata={"facility_id": payload.facility_id}, session=session)
    return {"work_order_id": work_order_id, "status": "completed_pending_release", "completed_at": now}

@router.post("/work-orders/{work_order_id}/release")
async def release_asset(work_order_id: str, payload: AssetRelease, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, RELEASE_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            order = await db.facility_work_orders.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "work_order_id": work_order_id, "status": "completed_pending_release"}, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Work order awaiting independent release not found")
            if order.get("completed_by_subject") == principal.subject:
                raise HTTPException(status_code=403, detail="Technician cannot independently release their own work")
            asset = await db.facility_assets.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "asset_id": order["asset_id"], "status": "maintenance"}, session=session)
            if asset is None:
                raise HTTPException(status_code=409, detail="Asset is not awaiting maintenance release")
            changed = await db.facility_work_orders.update_one({"_id": order["_id"], "status": "completed_pending_release"},
                {"$set": {"status": "released", "release_checklist_reference": payload.release_checklist_reference,
                    "release_rationale": payload.rationale, "released_at": now,
                    "released_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Work order state changed; retry")
            await db.facility_assets.update_one({"_id": asset["_id"], "status": "maintenance"},
                {"$set": {"status": "in_service", "last_released_at": now}}, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="facility.asset.release", resource_type="facility_asset", resource_id=order["asset_id"],
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "work_order_id": work_order_id}, session=session)
    return {"work_order_id": work_order_id, "asset_id": order["asset_id"], "status": "released", "released_at": now}
