"""Platform registry routes. Global mutations require verified platform-admin identity."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError
from odei_api.audit import append_audit_event
from odei_api.schemas import TenantCreate, OrganizationCreate, FacilityCreate
from odei_api.security import Principal, require_platform_admin

router = APIRouter(prefix="/control-plane", tags=["control-plane"])


def database(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _insert_with_audit(request, collection: str, record: dict, *, actor: str,
                             action: str, resource_type: str, resource_id: str,
                             tenant_id: str):
    db = database(request)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            await db[collection].insert_one(record, session=session)
            await append_audit_event(
                db, actor_id=actor, action=action, resource_type=resource_type,
                resource_id=resource_id, tenant_id=tenant_id, outcome="success",
                session=session,
            )


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, request: Request,
                        principal: Principal = Depends(require_platform_admin)):
    now = datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "status": "active", "created_at": now, "created_by": principal.subject,
    }
    try:
        await _insert_with_audit(
            request, "tenants", record, actor=principal.subject, action="tenant.create",
            resource_type="tenant", resource_id=payload.tenant_id, tenant_id=payload.tenant_id,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Tenant already exists") from exc
    return {"tenant_id": payload.tenant_id, "status": "active"}


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationCreate, request: Request,
                             principal: Principal = Depends(require_platform_admin)):
    db = database(request)
    tenant = await db.tenants.find_one({"tenant_id": payload.tenant_id, "status": "active"})
    if not tenant:
        raise HTTPException(status_code=404, detail="Active tenant not found")
    now = datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "status": "active", "created_at": now, "created_by": principal.subject,
    }
    try:
        await _insert_with_audit(
            request, "organizations", record, actor=principal.subject,
            action="organization.create", resource_type="organization",
            resource_id=payload.organization_id, tenant_id=payload.tenant_id,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Organization already exists") from exc
    return {"organization_id": payload.organization_id, "status": "active"}


@router.post("/facilities", status_code=status.HTTP_201_CREATED)
async def create_facility(payload: FacilityCreate, request: Request,
                          principal: Principal = Depends(require_platform_admin)):
    db = database(request)
    org = await db.organizations.find_one({
        "tenant_id": payload.tenant_id,
        "organization_id": payload.organization_id,
        "status": "active",
    })
    if not org:
        raise HTTPException(status_code=404, detail="Active organization not found")
    now = datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "status": "active", "created_at": now, "created_by": principal.subject,
    }
    try:
        await _insert_with_audit(
            request, "facilities", record, actor=principal.subject,
            action="facility.create", resource_type="facility",
            resource_id=payload.facility_id, tenant_id=payload.tenant_id,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Facility already exists") from exc
    return {"facility_id": payload.facility_id, "status": "active"}
