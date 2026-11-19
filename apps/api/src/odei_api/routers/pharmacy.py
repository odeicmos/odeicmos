"""Medication order and stock-backed dispensing foundation.

Medication safety checks, formulary, allergy reconciliation, controlled-drug
registers and jurisdictional pharmacy rules are separate required capabilities.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo import ASCENDING
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/pharmacy", tags=["pharmacy"])
PRESCRIBER_ROLES = ["facility_admin", "clinician"]
DISPENSER_ROLES = ["facility_admin", "pharmacist"]


class MedicationLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medication_code: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=2, max_length=200)
    dose: str = Field(min_length=1, max_length=100)
    route: str = Field(min_length=1, max_length=60)
    frequency: str = Field(min_length=1, max_length=100)
    duration: str | None = Field(default=None, max_length=100)
    quantity: int = Field(gt=0, le=10000)
    instructions: str | None = Field(default=None, max_length=1000)


class MedicationOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    lines: list[MedicationLine] = Field(min_length=1, max_length=50)


class DispenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_medication_order(
    payload: MedicationOrderCreate, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, PRESCRIBER_ROLES
    )
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
        raise HTTPException(status_code=404, detail="Active patient or open encounter not found")
    order_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "order_id": order_id, "status": "pending",
        "created_at": now, "prescriber_issuer": principal.issuer,
        "prescriber_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.medication_orders.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="medication_order.create", resource_type="medication_order",
                resource_id=order_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "line_count": len(payload.lines)},
                session=session,
            )
    return {"order_id": order_id, "status": "pending", "created_at": now}


@router.post("/orders/{order_id}/dispense", status_code=status.HTTP_201_CREATED)
async def dispense_medication_order(
    order_id: str, payload: DispenseRequest, request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _db(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, DISPENSER_ROLES
    )
    order = await db.medication_orders.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "order_id": order_id, "status": "pending",
    })
    if order is None:
        raise HTTPException(status_code=404, detail="Pending medication order not found")
    now, allocations = datetime.now(timezone.utc), []
    client = request.app.state.mongo_client
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                for line in order["lines"]:
                    remaining = line["quantity"]
                    lots = db.inventory_lots.find({
                        "tenant_id": payload.tenant_id,
                        "facility_id": payload.facility_id,
                        "medication_code": line["medication_code"],
                        "status": "active", "quantity_on_hand": {"$gt": 0},
                        "$or": [{"expiry_at": {"$gt": now}}, {"expiry_at": {"$exists": False}}],
                    }, session=session).sort([("expiry_at", ASCENDING), ("received_at", ASCENDING)])
                    async for lot in lots:
                        take = min(remaining, int(lot["quantity_on_hand"]))
                        changed = await db.inventory_lots.update_one({
                            "_id": lot["_id"], "quantity_on_hand": {"$gte": take},
                            "status": "active",
                            "$or": [{"expiry_at": {"$gt": now}}, {"expiry_at": {"$exists": False}}],
                        }, {"$inc": {"quantity_on_hand": -take}}, session=session)
                        if changed.modified_count != 1:
                            continue
                        allocations.append({
                            "medication_code": line["medication_code"],
                            "lot_id": lot["lot_id"], "batch_number": lot["batch_number"],
                            "quantity": take,
                        })
                        remaining -= take
                        if remaining == 0:
                            break
                    if remaining:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Insufficient unexpired stock for medication {line['medication_code']}",
                        )
                result = await db.medication_orders.update_one({
                    "_id": order["_id"], "status": "pending",
                }, {"$set": {
                    "status": "dispensed", "dispensed_at": now,
                    "dispensed_by_issuer": principal.issuer,
                    "dispensed_by_subject": principal.subject,
                    "dispense_allocations": allocations,
                }}, session=session)
                if result.modified_count != 1:
                    raise HTTPException(status_code=409, detail="Medication order was already processed")
                dispense_id = str(uuid4())
                await db.dispensing_events.insert_one({
                    "dispense_id": dispense_id, "order_id": order_id,
                    "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                    "patient_id": order["patient_id"], "allocations": allocations,
                    "occurred_at": now, "actor_issuer": principal.issuer,
                    "actor_subject": principal.subject,
                }, session=session)
                for allocation in allocations:
                    await db.inventory_movements.insert_one({
                        "movement_id": str(uuid4()), "tenant_id": payload.tenant_id,
                        "facility_id": payload.facility_id,
                        "item_code": allocation["medication_code"],
                        "medication_code": allocation["medication_code"],
                        "lot_id": allocation["lot_id"], "movement_type": "dispensing",
                        "quantity_delta": -allocation["quantity"], "source_id": dispense_id,
                        "occurred_at": now, "actor_issuer": principal.issuer,
                        "actor_subject": principal.subject,
                    }, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="medication_order.dispense", resource_type="medication_order",
                    resource_id=order_id, tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id, "allocation_count": len(allocations)},
                    session=session,
                )
    except HTTPException:
        raise
    return {"order_id": order_id, "status": "dispensed",
            "allocations": allocations, "dispensed_at": now}
