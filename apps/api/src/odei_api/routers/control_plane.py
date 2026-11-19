"""Platform registry routes. Only verified platform administrators may mutate global registry."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError
from odei_api.audit import append_audit_event
from odei_api.schemas import OrganizationCreate, FacilityCreate
from odei_api.security import Principal, require_platform_admin

router = APIRouter(prefix="/control-plane", tags=["control-plane"])


def database(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate, request: Request,
    principal: Principal = Depends(require_platform_admin),
):
    db = database(request)
    tenant = await db.tenants.find_one({"tenant_id": payload.tenant_id, "status": "active"})
    if not tenant:
        raise HTTPException(status_code=404, detail="Active tenant not found")
    now = datetime.now(timezone.utc)
    record = payload.model_dump() | {
        "status": "active", "created_at": now, "created_by": principal.subject,
    }
    try:
        await db.organizations.insert_one(record)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Organization already exists") from exc
    await append_audit_event(
        db, actor_id=principal.subject, action="organization.create",
        resource_type="organization", resource_id=payload.organization_id,
        tenant_id=payload.tenant_id, outcome="success",
    )
    return {"organization_id": payload.organization_id, "status": "active"}


@router.post("/facilities", status_code=status.HTTP_201_CREATED)
async def create_facility(
    payload: FacilityCreate, request: Request,
    principal: Principal = Depends(require_platform_admin),
):
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
        await db.facilities.insert_one(record)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Facility already exists") from exc
    await append_audit_event(
        db, actor_id=principal.subject, action="facility.create",
        resource_type="facility", resource_id=payload.facility_id,
        tenant_id=payload.tenant_id, outcome="success",
    )
    return {"facility_id": payload.facility_id, "status": "active"}
