"""Patient registration endpoints with facility-scoped access and audited writes."""
from datetime import date, datetime, time, timezone
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pymongo.errors import DuplicateKeyError

from odei_api.audit import append_audit_event
from odei_api.schemas import PatientRegistrationCreate
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/patients", tags=["patient-registration"])
REGISTRATION_ROLES = ["facility_admin", "clinician", "nurse", "receptionist"]



class PatientMatchReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    patient_id: str = Field(min_length=1, max_length=64)
    candidate_patient_id: str = Field(min_length=1, max_length=64)
    outcome: Literal["same_person", "different_person", "needs_more_information"]
    rationale: str = Field(min_length=10, max_length=2000)

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
    if payload.date_of_birth is not None:
        record["date_of_birth"] = datetime.combine(payload.date_of_birth, time.min, tzinfo=timezone.utc)
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
    role = await authorize_facility_access(
        request, principal, tenant_id, facility_id,
        ["facility_admin", "clinician", "nurse", "receptionist", "auditor"],
    )
    projection = {"_id": 0}
    if role == "auditor":
        projection = {"_id": 0, "patient_id": 1, "medical_record_number": 1,
                      "created_at": 1, "record_status": 1}
    elif role == "receptionist":
        projection = {"_id": 0, "patient_id": 1, "medical_record_number": 1,
                      "legal_name": 1, "preferred_name": 1, "date_of_birth": 1,
                      "phone_number": 1, "preferred_language": 1, "record_status": 1}
    patient = await db.patients.find_one({
        "patient_id": patient_id,
        "tenant_id": tenant_id,
        "facility_id": facility_id,
        "record_status": "active",
    }, projection=projection)
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

@router.get("/identity-match/candidates")
async def find_identity_match_candidates(tenant_id: str, facility_id: str, request: Request,
    medical_record_number: str | None = None, phone_number: str | None = None,
    date_of_birth: date | None = None, principal: Principal = Depends(require_principal)):
    db = _database(request)
    await authorize_facility_access(request, principal, tenant_id, facility_id, REGISTRATION_ROLES)
    if not medical_record_number and not (phone_number and date_of_birth):
        raise HTTPException(status_code=422, detail="Provide MRN or both phone number and date of birth")
    if date_of_birth and date_of_birth > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Date of birth cannot be in the future")
    clauses = []
    if medical_record_number:
        clauses.append({"medical_record_number": medical_record_number.strip()})
    if phone_number and date_of_birth:
        dob = datetime.combine(date_of_birth, time.min, tzinfo=timezone.utc)
        clauses.append({"phone_number": phone_number.strip(), "date_of_birth": dob})
    candidates = await db.patients.find({"tenant_id": tenant_id, "facility_id": facility_id,
        "record_status": "active", "$or": clauses},
        projection={"_id": 0, "patient_id": 1, "medical_record_number": 1,
            "legal_name": 1, "preferred_name": 1, "date_of_birth": 1, "phone_number": 1}
    ).limit(10).to_list(length=10)
    await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
        action="patient.identity_match.search", resource_type="patient_identity_match",
        resource_id="query", tenant_id=tenant_id, outcome="success",
        metadata={"facility_id": facility_id, "candidate_count": len(candidates)})
    return {"candidates": candidates, "review_required": bool(candidates),
        "automatic_merge_performed": False}

@router.post("/identity-match/reviews", status_code=status.HTTP_201_CREATED)
async def record_identity_match_review(payload: PatientMatchReview, request: Request,
    principal: Principal = Depends(require_principal)):
    db = _database(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id,
        ["facility_admin", "clinician", "nurse", "receptionist", "medical_records_officer"])
    if payload.patient_id == payload.candidate_patient_id:
        raise HTTPException(status_code=422, detail="A patient cannot be matched against itself")
    ids = [payload.patient_id, payload.candidate_patient_id]
    patients = await db.patients.find({"tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "patient_id": {"$in": ids}, "record_status": "active"}, projection={"patient_id": 1}).to_list(length=2)
    if len(patients) != 2:
        raise HTTPException(status_code=404, detail="Both active patient records must exist in this facility")
    review_id, now = str(uuid4()), datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.patient_identity_reviews.insert_one(payload.model_dump() | {
                "review_id": review_id, "reviewed_at": now,
                "reviewer_issuer": principal.issuer, "reviewer_subject": principal.subject}, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="patient.identity_match.review", resource_type="patient_identity_review",
                resource_id=review_id, tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "outcome": payload.outcome}, session=session)
    return {"review_id": review_id, "outcome": payload.outcome, "reviewed_at": now,
        "records_merged": False}
