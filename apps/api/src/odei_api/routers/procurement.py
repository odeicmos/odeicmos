"""Procurement and stock-receipt workflow foundation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/procurement", tags=["procurement"])
BUYER_ROLES = ["facility_admin", "procurement_officer"]
RECEIVER_ROLES = ["facility_admin", "procurement_officer", "pharmacist"]


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    supplier_code: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    tax_reference: str | None = Field(default=None, max_length=100)
    payment_terms: str | None = Field(default=None, max_length=120)


class PurchaseOrderAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    reason: str | None = Field(default=None, max_length=1000)


class PurchaseOrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_code: str = Field(min_length=1, max_length=80)
    item_name: str = Field(min_length=2, max_length=160)
    quantity: int = Field(gt=0, le=100000)
    unit_cost_minor: int = Field(ge=0, le=10**12)


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    supplier_id: str = Field(min_length=1, max_length=64)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    lines: list[PurchaseOrderLine] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class GoodsReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    purchase_order_id: str = Field(min_length=1, max_length=64)
    item_code: str = Field(min_length=1, max_length=80)
    quantity_received: int = Field(gt=0, le=100000)
    lot_number: str = Field(min_length=1, max_length=100)
    expiry_date: datetime | None = None
    unit_cost_minor: int = Field(ge=0, le=10**12)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
async def create_purchase_order(payload: PurchaseOrderCreate, request: Request,
                               principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, BUYER_ROLES)
    total = sum(line.quantity * line.unit_cost_minor for line in payload.lines)
    if total > 10**12:
        raise HTTPException(status_code=422, detail="Purchase order total exceeds supported limit")
    order_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "purchase_order_id": order_id, "total_minor": total, "status": "draft",
        "created_at": now, "created_by_issuer": principal.issuer,
        "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db.purchase_orders.insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="purchase_order.create", resource_type="purchase_order",
                resource_id=order_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "total_minor": total},
                session=session,
            )
    return {"purchase_order_id": order_id, "status": "draft",
            "total_minor": total, "currency": payload.currency}


@router.post("/goods-receipts", status_code=status.HTTP_201_CREATED)
async def receive_goods(payload: GoodsReceiptCreate, request: Request,
                        principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, RECEIVER_ROLES)
    if payload.expiry_date and payload.expiry_date.tzinfo is None:
        raise HTTPException(status_code=422, detail="Expiry timestamp must include timezone")
    now = datetime.now(timezone.utc)
    if payload.expiry_date and payload.expiry_date <= now:
        raise HTTPException(status_code=422, detail="Cannot receive an expired lot")
    receipt_id, lot_id = str(uuid4()), str(uuid4())
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            order = await db.purchase_orders.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "purchase_order_id": payload.purchase_order_id,
                "status": "approved_for_receipt",
            }, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Receivable purchase order not found")
            line = next((x for x in order["lines"] if x["item_code"] == payload.item_code), None)
            if line is None or payload.unit_cost_minor != line["unit_cost_minor"]:
                raise HTTPException(status_code=409, detail="Item or unit cost does not match purchase order")
            already = await db.goods_receipts.aggregate([
                {"$match": {"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                            "purchase_order_id": payload.purchase_order_id, "item_code": payload.item_code}},
                {"$group": {"_id": None, "quantity": {"$sum": "$quantity_received"}}},
            ], session=session).to_list(length=1)
            received = already[0]["quantity"] if already else 0
            if received + payload.quantity_received > line["quantity"]:
                raise HTTPException(status_code=409, detail="Receipt exceeds ordered quantity")
            await db.goods_receipts.insert_one(payload.model_dump() | {
                "receipt_id": receipt_id, "received_at": now,
                "received_by_issuer": principal.issuer, "received_by_subject": principal.subject,
            }, session=session)
            await db.inventory_lots.insert_one({
                "lot_id": lot_id, "tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "item_code": payload.item_code,
                "lot_number": payload.lot_number, "batch_number": payload.lot_number,
                "item_code": payload.item_code, "medication_code": payload.item_code,
                "quantity_available": payload.quantity_received,
                "quantity_on_hand": payload.quantity_received,
                "unit_cost_minor": payload.unit_cost_minor,
                "expiry_date": payload.expiry_date, "expiry_at": payload.expiry_date or datetime.max.replace(tzinfo=timezone.utc),
                "status": "active", "received_at": now, "receipt_id": receipt_id,
            }, session=session)
            await db.inventory_movements.insert_one({
                "movement_id": str(uuid4()), "tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "item_code": payload.item_code,
                "medication_code": payload.item_code, "lot_id": lot_id,
                "movement_type": "goods_receipt", "quantity_delta": payload.quantity_received,
                "unit_cost_minor": payload.unit_cost_minor, "source_id": receipt_id,
                "occurred_at": now, "actor_issuer": principal.issuer,
                "actor_subject": principal.subject,
            }, session=session)
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="goods_receipt.record", resource_type="goods_receipt",
                resource_id=receipt_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "lot_id": lot_id,
                          "quantity": payload.quantity_received}, session=session,
            )
    return {"receipt_id": receipt_id, "lot_id": lot_id, "quantity_received": payload.quantity_received}


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
async def create_supplier(payload: SupplierCreate, request: Request,
                          principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    ["facility_admin", "procurement_officer"])
    supplier_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "supplier_id": supplier_id, "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    client = request.app.state.mongo_client
    try:
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db.suppliers.insert_one(record, session=session)
                await append_audit_event(
                    db, actor_id=f"{principal.issuer}|{principal.subject}",
                    action="supplier.create", resource_type="supplier", resource_id=supplier_id,
                    tenant_id=payload.tenant_id, outcome="success",
                    metadata={"facility_id": payload.facility_id, "supplier_code": payload.supplier_code},
                    session=session,
                )
    except Exception as exc:
        if exc.__class__.__name__ == "DuplicateKeyError":
            raise HTTPException(status_code=409, detail="Supplier code already exists") from exc
        raise
    return {"supplier_id": supplier_id, "supplier_code": payload.supplier_code, "status": "active"}


@router.post("/purchase-orders/{purchase_order_id}/submit")
async def submit_purchase_order(purchase_order_id: str, payload: PurchaseOrderAction,
                                request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, BUYER_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            order = await db.purchase_orders.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "purchase_order_id": purchase_order_id, "status": "draft",
            }, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Draft purchase order not found")
            supplier = await db.suppliers.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "supplier_id": order["supplier_id"], "status": "active",
            }, session=session, projection={"_id": 1})
            if supplier is None:
                raise HTTPException(status_code=409, detail="Purchase order supplier is not active")
            changed = await db.purchase_orders.update_one(
                {"_id": order["_id"], "status": "draft"},
                {"$set": {"status": "pending_approval", "submitted_at": now,
                          "submitted_by_subject": principal.subject}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Purchase order state changed; retry")
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="purchase_order.submit", resource_type="purchase_order",
                resource_id=purchase_order_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id}, session=session,
            )
    return {"purchase_order_id": purchase_order_id, "status": "pending_approval", "submitted_at": now}


@router.post("/purchase-orders/{purchase_order_id}/approve")
async def approve_purchase_order(purchase_order_id: str, payload: PurchaseOrderAction,
                                 request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    ["facility_admin", "finance_officer"])
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            order = await db.purchase_orders.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "purchase_order_id": purchase_order_id, "status": "pending_approval",
            }, session=session)
            if order is None:
                raise HTTPException(status_code=404, detail="Purchase order awaiting approval not found")
            if order.get("created_by_issuer") == principal.issuer and order.get("created_by_subject") == principal.subject:
                raise HTTPException(status_code=403, detail="Purchase order creator cannot approve their own order")
            changed = await db.purchase_orders.update_one(
                {"_id": order["_id"], "status": "pending_approval"},
                {"$set": {"status": "approved_for_receipt", "approved_at": now,
                          "approved_by_issuer": principal.issuer,
                          "approved_by_subject": principal.subject,
                          "approval_reason": payload.reason}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Purchase order state changed; retry")
            await append_audit_event(
                db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="purchase_order.approve", resource_type="purchase_order",
                resource_id=purchase_order_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "total_minor": order["total_minor"]},
                session=session,
            )
    return {"purchase_order_id": purchase_order_id, "status": "approved_for_receipt", "approved_at": now}
