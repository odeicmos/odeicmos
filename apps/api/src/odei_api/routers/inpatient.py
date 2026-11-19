"""Inpatient bed and admission lifecycle foundation with atomic bed allocation."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/inpatient", tags=["inpatient"])
ADMIN_ROLES = ["facility_admin"]
ADMISSION_ROLES = ["facility_admin", "clinician"]
WARD_ROLES = ["facility_admin", "nurse"]


class BedCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    ward_code: str = Field(min_length=1, max_length=64)
    ward_name: str = Field(min_length=2, max_length=120)
    bed_code: str = Field(min_length=1, max_length=64)
    bed_type: Literal["general", "maternity", "paediatric", "icu", "isolation", "other"] = "general"


class AdmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    bed_code: str = Field(min_length=1, max_length=64)
    admission_reason: str = Field(min_length=3, max_length=2000)


class BedTransfer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    destination_bed_code: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=3, max_length=1000)


class DischargeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    discharge_disposition: Literal["home", "transfer", "referred", "died", "other"]
    summary: str = Field(min_length=3, max_length=5000)


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, kind, resource_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
        action=action, resource_type=kind, resource_id=resource_id,
        tenant_id=tenant_id, outcome="success",
        metadata={"facility_id": facility_id, **(metadata or {})}, session=session)


@router.post("/beds", status_code=status.HTTP_201_CREATED)
async def create_bed(payload: BedCreate, request: Request,
                     principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ADMIN_ROLES)
    bed_id, now = str(uuid4()), datetime.now(timezone.utc)
    record = payload.model_dump() | {"bed_id": bed_id, "status": "available", "created_at": now}
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            if await db.beds.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                                       "bed_code": payload.bed_code}, session=session):
                raise HTTPException(status_code=409, detail="Bed code already exists")
            await db.beds.insert_one(record, session=session)
            await _audit(db, session, principal, "inpatient.bed.create", "bed", bed_id,
                         payload.tenant_id, payload.facility_id)
    return {"bed_id": bed_id, "bed_code": payload.bed_code, "status": "available"}


@router.post("/admissions", status_code=status.HTTP_201_CREATED)
async def admit_patient(payload: AdmissionCreate, request: Request,
                        principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ADMISSION_ROLES)
    patient = await db.patients.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "record_status": "active"}, projection={"_id": 1})
    encounter = await db.encounters.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": payload.patient_id, "encounter_id": payload.encounter_id,
        "encounter_type": "inpatient", "status": "open"}, projection={"_id": 1})
    if patient is None or encounter is None:
        raise HTTPException(status_code=404, detail="Active patient and open inpatient encounter are required")
    admission_id, now = str(uuid4()), datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            bed = await db.beds.find_one({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "bed_code": payload.bed_code, "status": "available"}, session=session)
            if bed is None:
                raise HTTPException(status_code=409, detail="Bed is unavailable or not configured")
            changed = await db.beds.update_one({"_id": bed["_id"], "status": "available"},
                {"$set": {"status": "occupied", "current_admission_id": admission_id,
                          "updated_at": now}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Bed allocation conflict")
            await db.admissions.insert_one(payload.model_dump() | {
                "admission_id": admission_id, "status": "admitted", "bed_code": payload.bed_code,
                "admitted_at": now, "admitting_issuer": principal.issuer,
                "admitting_subject": principal.subject,
            }, session=session)
            await _audit(db, session, principal, "inpatient.admit", "admission", admission_id,
                         payload.tenant_id, payload.facility_id, {"bed_code": payload.bed_code})
    return {"admission_id": admission_id, "bed_code": payload.bed_code,
            "status": "admitted", "admitted_at": now}


@router.post("/admissions/{admission_id}/transfer")
async def transfer_patient(admission_id: str, payload: BedTransfer, request: Request,
                           principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, WARD_ROLES)
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            admission = await db.admissions.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "admission_id": admission_id,
                "status": "admitted"}, session=session)
            if admission is None:
                raise HTTPException(status_code=404, detail="Active admission not found")
            if admission["bed_code"] == payload.destination_bed_code:
                raise HTTPException(status_code=409, detail="Patient is already assigned to this bed")
            destination = await db.beds.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "bed_code": payload.destination_bed_code,
                "status": "available"}, session=session)
            current = await db.beds.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "bed_code": admission["bed_code"],
                "status": "occupied", "current_admission_id": admission_id}, session=session)
            if destination is None or current is None:
                raise HTTPException(status_code=409, detail="Source or destination bed state is inconsistent")
            allocated = await db.beds.update_one({"_id": destination["_id"], "status": "available"},
                {"$set": {"status": "occupied", "current_admission_id": admission_id,
                          "updated_at": now}}, session=session)
            released = await db.beds.update_one({"_id": current["_id"], "status": "occupied",
                "current_admission_id": admission_id},
                {"$set": {"status": "available", "current_admission_id": None,
                          "updated_at": now}}, session=session)
            if allocated.modified_count != 1 or released.modified_count != 1:
                raise HTTPException(status_code=409, detail="Bed transfer conflict; transaction rolled back")
            await db.admissions.update_one({"_id": admission["_id"], "status": "admitted"},
                {"$set": {"bed_code": payload.destination_bed_code, "updated_at": now}}, session=session)
            await db.admission_transfers.insert_one({"transfer_id": str(uuid4()),
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "admission_id": admission_id, "from_bed_code": admission["bed_code"],
                "to_bed_code": payload.destination_bed_code, "reason": payload.reason,
                "transferred_at": now, "actor_subject": principal.subject}, session=session)
            await _audit(db, session, principal, "inpatient.transfer", "admission", admission_id,
                         payload.tenant_id, payload.facility_id,
                         {"from_bed": admission["bed_code"], "to_bed": payload.destination_bed_code})
    return {"admission_id": admission_id, "bed_code": payload.destination_bed_code,
            "status": "admitted", "transferred_at": now}


@router.post("/admissions/{admission_id}/discharge")
async def discharge_patient(admission_id: str, payload: DischargeCreate, request: Request,
                            principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
                                    ["facility_admin", "clinician"])
    now = datetime.now(timezone.utc)
    client = request.app.state.mongo_client
    async with await client.start_session() as session:
        async with session.start_transaction():
            admission = await db.admissions.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "admission_id": admission_id,
                "status": "admitted"}, session=session)
            if admission is None:
                raise HTTPException(status_code=404, detail="Active admission not found")
            bed = await db.beds.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "bed_code": admission["bed_code"],
                "status": "occupied", "current_admission_id": admission_id}, session=session)
            if bed is None:
                raise HTTPException(status_code=409, detail="Assigned bed state is inconsistent")
            released = await db.beds.update_one({"_id": bed["_id"], "status": "occupied",
                "current_admission_id": admission_id},
                {"$set": {"status": "available", "current_admission_id": None,
                          "updated_at": now}}, session=session)
            discharged = await db.admissions.update_one({"_id": admission["_id"], "status": "admitted"},
                {"$set": {"status": "discharged", "discharged_at": now,
                          "discharge_disposition": payload.discharge_disposition,
                          "discharge_summary": payload.summary}}, session=session)
            if released.modified_count != 1 or discharged.modified_count != 1:
                raise HTTPException(status_code=409, detail="Discharge state changed; transaction rolled back")
            await db.encounters.update_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "encounter_id": admission["encounter_id"],
                "status": "open"}, {"$set": {"status": "closed", "ended_at": now,
                "discharge_disposition": payload.discharge_disposition}}, session=session)
            await _audit(db, session, principal, "inpatient.discharge", "admission", admission_id,
                         payload.tenant_id, payload.facility_id)
    return {"admission_id": admission_id, "status": "discharged", "discharged_at": now}
