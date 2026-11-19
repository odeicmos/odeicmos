"""Patient registration endpoints with facility-scoped access and audited writes."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.schemas import PatientRegistrationCreate
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/patients", tags=["patient-registration"])
REGISTRATION_ROLES = ["facility_admin", "clinician", "nurse", "receptionist"]


def _database(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_patient(
    payload: PatientRegistrationCreate,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _database(request)
    await authorize_facility_access(
        request, principal, payload.tenant_id, payload.facility_id, REGISTRATION_ROLES
    )
    facility = await db.facilities.find_one({
        "tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id,
        "status": "active",
    }, projection={"_id": 0, "facility_id": 1})
    if facility is None:
        raise HTTPException(status_code=404, detail="Active facility not found")
    if payload.date_of_birth and payload.date_of_birth > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Date of birth cannot be in the future")

    patient_id = str(uuid4())
    now = datetime.now(timezone.utc)
    record = payload.model_dump(exclude={"tenant_id", "facility_id"}) | {
        "patient_id": patient_id,
        "tenant_id": payload.tenant_id,
        "facility_id": payload.facility_id,
        "created_at": now,
        "created_by_issuer": principal.issuer,
        "created_by_subject": principal.subject,
        "record_status": "active",
    }
    try:
        client = request.app.state.mongo_client
        async with await client.start_session() as session:
            async with session.start_transaction():
                await db.patients.insert_one(record, session=session)
                await append_audit_event(
                    db,
                    actor_id=f"{principal.issuer}|{principal.subject}",
                    action="patient.register",
                    resource_type="patient",
                    resource_id=patient_id,
                    tenant_id=payload.tenant_id,
                    outcome="success",
                    metadata={"facility_id": payload.facility_id},
                    session=session,
                )
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Medical record number already exists at this facility") from exc
    return {
        "patient_id": patient_id,
        "medical_record_number": payload.medical_record_number,
        "facility_id": payload.facility_id,
        "record_status": "active",
        "created_at": now,
    }


@router.get("/{patient_id}")
async def get_patient(
    patient_id: str,
    tenant_id: str,
    facility_id: str,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    db = _database(request)
    await authorize_facility_access(
        request, principal, tenant_id, facility_id,
        ["facility_admin", "clinician", "nurse", "receptionist", "auditor", "read_only"],
    )
    patient = await db.patients.find_one({
        "patient_id": patient_id,
        "tenant_id": tenant_id,
        "facility_id": facility_id,
        "record_status": "active",
    }, projection={"_id": 0})
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    await append_audit_event(
        db,
        actor_id=f"{principal.issuer}|{principal.subject}",
        action="patient.read",
        resource_type="patient",
        resource_id=patient_id,
        tenant_id=tenant_id,
        outcome="success",
        metadata={"facility_id": facility_id},
    )
    return patient
