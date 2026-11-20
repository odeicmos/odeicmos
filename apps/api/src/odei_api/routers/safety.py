"""Append-only quality, safety and incident investigation workflow."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/safety", tags=["quality-and-safety"])
REPORT_ROLES = ["facility_admin", "clinician", "nurse", "pharmacist", "lab_scientist", "vaccinator"]
INVESTIGATION_ROLES = ["facility_admin", "quality_officer", "clinical_governance_officer"]

class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    category: Literal["clinical_safety", "medication", "laboratory", "infection", "equipment", "privacy", "security", "complaint", "near_miss", "other"]
    severity: Literal["near_miss", "low", "moderate", "high", "critical"]
    occurred_at: datetime
    location_code: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=10, max_length=2000)
    immediate_actions: str | None = Field(default=None, max_length=2000)
    patient_reference: str | None = Field(default=None, max_length=100)
    confidential: bool = True

class InvestigationNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    note_type: Literal["finding", "interview", "evidence", "risk_control", "corrective_action"]
    note: str = Field(min_length=10, max_length=5000)
    evidence_reference: str | None = Field(default=None, max_length=300)

class IncidentClose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    root_cause_summary: str = Field(min_length=20, max_length=4000)
    corrective_action_summary: str = Field(min_length=20, max_length=4000)
    residual_risk: Literal["none", "low", "moderate", "high"]
    evidence_reference: str = Field(min_length=8, max_length=300)

def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db

@router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def report_incident(payload: IncidentCreate, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, REPORT_ROLES)
    if payload.occurred_at.tzinfo is None or payload.occurred_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="occurred_at must include timezone")
    now, incident_id = datetime.now(timezone.utc), str(uuid4())
    if payload.occurred_at > now:
        raise HTTPException(status_code=422, detail="Incident occurrence cannot be in the future")
    record = payload.model_dump() | {"incident_id": incident_id, "status": "reported",
        "reported_at": now, "reporter_issuer": principal.issuer, "reporter_subject": principal.subject}
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await db.safety_incidents.insert_one(record, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="safety.incident.report", resource_type="safety_incident", resource_id=incident_id,
                tenant_id=payload.tenant_id, outcome="success",
                metadata={"facility_id": payload.facility_id, "category": payload.category,
                          "severity": payload.severity, "confidential": payload.confidential}, session=session)
    return {"incident_id": incident_id, "status": "reported", "reported_at": now}

@router.post("/incidents/{incident_id}/investigate")
async def start_investigation(incident_id: str, payload: InvestigationNote, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, INVESTIGATION_ROLES)
    now, note_id = datetime.now(timezone.utc), str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            incident = await db.safety_incidents.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "incident_id": incident_id,
                "status": {"$in": ["reported", "investigating"]}}, session=session)
            if incident is None:
                raise HTTPException(status_code=404, detail="Open safety incident not found")
            if incident.get("reporter_subject") == principal.subject and incident.get("reporter_issuer") == principal.issuer:
                raise HTTPException(status_code=403, detail="Reporter cannot lead the investigation of their own incident")
            await db.safety_investigation_notes.insert_one(payload.model_dump() | {
                "note_id": note_id, "incident_id": incident_id, "recorded_at": now,
                "recorded_by_issuer": principal.issuer, "recorded_by_subject": principal.subject}, session=session)
            await db.safety_incidents.update_one({"_id": incident["_id"], "status": "reported"},
                {"$set": {"status": "investigating", "investigation_started_at": now,
                    "investigation_lead_subject": principal.subject}}, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="safety.incident.investigate", resource_type="safety_incident", resource_id=incident_id,
                tenant_id=payload.tenant_id, outcome="success", metadata={"facility_id": payload.facility_id,
                    "note_type": payload.note_type}, session=session)
    return {"incident_id": incident_id, "note_id": note_id, "status": "investigating", "recorded_at": now}

@router.post("/incidents/{incident_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_investigation_note(incident_id: str, payload: InvestigationNote, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, INVESTIGATION_ROLES)
    now, note_id = datetime.now(timezone.utc), str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            incident = await db.safety_incidents.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "incident_id": incident_id, "status": "investigating"}, session=session)
            if incident is None:
                raise HTTPException(status_code=404, detail="Incident is not under investigation")
            await db.safety_investigation_notes.insert_one(payload.model_dump() | {
                "note_id": note_id, "incident_id": incident_id, "recorded_at": now,
                "recorded_by_issuer": principal.issuer, "recorded_by_subject": principal.subject}, session=session)
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="safety.incident.note", resource_type="safety_investigation_note", resource_id=note_id,
                tenant_id=payload.tenant_id, outcome="success", metadata={"facility_id": payload.facility_id,
                    "incident_id": incident_id, "note_type": payload.note_type}, session=session)
    return {"incident_id": incident_id, "note_id": note_id, "recorded_at": now}

@router.post("/incidents/{incident_id}/close")
async def close_incident(incident_id: str, payload: IncidentClose, request: Request, principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, INVESTIGATION_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            incident = await db.safety_incidents.find_one({"tenant_id": payload.tenant_id,
                "facility_id": payload.facility_id, "incident_id": incident_id, "status": "investigating"}, session=session)
            if incident is None:
                raise HTTPException(status_code=404, detail="Incident under investigation not found")
            if incident.get("reporter_subject") == principal.subject and incident.get("reporter_issuer") == principal.issuer:
                raise HTTPException(status_code=403, detail="Reporter cannot close their own incident")
            changed = await db.safety_incidents.update_one({"_id": incident["_id"], "status": "investigating"},
                {"$set": {"status": "closed", "root_cause_summary": payload.root_cause_summary,
                    "corrective_action_summary": payload.corrective_action_summary,
                    "residual_risk": payload.residual_risk, "closure_evidence_reference": payload.evidence_reference,
                    "closed_at": now, "closed_by_issuer": principal.issuer, "closed_by_subject": principal.subject}}, session=session)
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Incident state changed; retry closure")
            await append_audit_event(db, actor_id=f"{principal.issuer}|{principal.subject}",
                action="safety.incident.close", resource_type="safety_incident", resource_id=incident_id,
                tenant_id=payload.tenant_id, outcome="success", metadata={"facility_id": payload.facility_id,
                    "residual_risk": payload.residual_risk}, session=session)
    return {"incident_id": incident_id, "status": "closed", "closed_at": now}
