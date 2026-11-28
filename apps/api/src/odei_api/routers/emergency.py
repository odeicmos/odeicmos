"""Emergency department episode, event log, handover and disposition workflows."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from odei_api.audit import append_audit_event
from odei_api.security import Principal, authorize_facility_access, require_principal

router = APIRouter(prefix="/emergency", tags=["emergency"])
ED_ROLES = ["facility_admin", "clinician", "nurse"]
DISPOSITION_ROLES = ["facility_admin", "clinician"]


class EmergencyEpisodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    encounter_id: str = Field(min_length=1, max_length=64)
    arrival_mode: Literal["walk_in", "ambulance", "referral", "police", "other"]
    arrival_at: datetime
    presenting_complaint: str = Field(min_length=2, max_length=2000)
    accompanying_person: str | None = Field(default=None, max_length=256)
    referral_source: str | None = Field(default=None, max_length=256)

    @field_validator("arrival_at")
    @classmethod
    def arrival_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("arrival_at must include timezone")
        return value


class EmergencyEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    event_type: Literal["resuscitation", "airway", "cardiac_arrest", "seizure",
                        "trauma", "hemorrhage", "deterioration", "procedure",
                        "senior_review", "other"]
    occurred_at: datetime
    summary: str = Field(min_length=3, max_length=3000)
    actions_taken: list[str] = Field(min_length=1, max_length=30)
    response: str = Field(min_length=2, max_length=2000)
    escalation_to: str | None = Field(default=None, max_length=256)

    @field_validator("occurred_at")
    @classmethod
    def event_time_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")
        return value


class EmergencyHandoverCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    receiving_service: str = Field(min_length=2, max_length=160)
    receiving_practitioner: str | None = Field(default=None, max_length=256)
    clinical_summary: str = Field(min_length=3, max_length=4000)
    outstanding_actions: list[str] = Field(default_factory=list, max_length=30)
    risk_flags: list[str] = Field(default_factory=list, max_length=20)


class EmergencyHandoverAcknowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    acknowledgement_note: str = Field(min_length=2, max_length=1000)


class EmergencyDispositionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=3, max_length=64)
    facility_id: str = Field(min_length=3, max_length=64)
    disposition: Literal["discharge", "admit", "transfer", "refer", "left_before_completion", "died"]
    rationale: str = Field(min_length=5, max_length=3000)
    destination: str | None = Field(default=None, max_length=256)
    transport_arrangement: str | None = Field(default=None, max_length=1000)
    follow_up_instructions: str | None = Field(default=None, max_length=3000)
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def decision_time_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must include timezone")
        return value


def _db(request: Request):
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return db


async def _audit(db, session, principal, action, resource_type, resource_id, tenant_id, facility_id, metadata=None):
    await append_audit_event(
        db, actor_id=f"{principal.issuer}|{principal.subject}", action=action,
        resource_type=resource_type, resource_id=resource_id, tenant_id=tenant_id,
        outcome="success", metadata={"facility_id": facility_id, **(metadata or {})},
        session=session,
    )


async def _episode(db, tenant_id, facility_id, episode_id, session=None):
    item = await db.emergency_episodes.find_one({
        "tenant_id": tenant_id, "facility_id": facility_id,
        "episode_id": episode_id,
    }, session=session)
    if item is None:
        raise HTTPException(status_code=404, detail="Emergency episode not found")
    return item


async def _touch_active_episode(db, episode, now, session):
    """Serialize active-episode child writes against terminal disposition."""
    changed = await db.emergency_episodes.update_one(
        {"_id": episode["_id"], "status": "active"},
        {"$inc": {"activity_revision": 1}, "$set": {"last_activity_at": now}},
        session=session,
    )
    if changed.modified_count != 1:
        raise HTTPException(status_code=409, detail="Emergency episode is no longer active")


@router.post("/episodes", status_code=status.HTTP_201_CREATED)
async def create_emergency_episode(payload: EmergencyEpisodeCreate, request: Request,
                                   principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ED_ROLES)
    encounter = await db.encounters.find_one({
        "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
        "encounter_id": payload.encounter_id, "encounter_type": "emergency", "status": "open",
    }, projection={"_id": 1, "patient_id": 1})
    if encounter is None:
        raise HTTPException(status_code=404, detail="Open emergency encounter not found")
    now = datetime.now(timezone.utc)
    if payload.arrival_at > now:
        raise HTTPException(status_code=422, detail="Arrival time cannot be in the future")
    episode_id = str(uuid4())
    record = payload.model_dump() | {
        "episode_id": episode_id, "patient_id": encounter["patient_id"],
        "status": "active", "created_at": now,
        "created_by_issuer": principal.issuer, "created_by_subject": principal.subject,
    }
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            existing = await db.emergency_episodes.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "encounter_id": payload.encounter_id,
            }, session=session)
            if existing:
                raise HTTPException(status_code=409, detail="Emergency episode already exists for this encounter")
            await db.emergency_episodes.insert_one(record, session=session)
            await _audit(db, session, principal, "emergency.episode.create", "emergency_episode",
                         episode_id, payload.tenant_id, payload.facility_id,
                         {"encounter_id": payload.encounter_id, "arrival_mode": payload.arrival_mode})
    return {"episode_id": episode_id, "encounter_id": payload.encounter_id, "status": "active"}


@router.post("/episodes/{episode_id}/events", status_code=status.HTTP_201_CREATED)
async def record_emergency_event(episode_id: str, payload: EmergencyEventCreate, request: Request,
                                 principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ED_ROLES)
    now = datetime.now(timezone.utc)
    if payload.occurred_at > now:
        raise HTTPException(status_code=422, detail="Event time cannot be in the future")
    event_id = str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            episode = await _episode(db, payload.tenant_id, payload.facility_id, episode_id, session)
            if episode["status"] != "active":
                raise HTTPException(status_code=409, detail="Emergency episode is not active")
            await _touch_active_episode(db, episode, now, session)
            record = payload.model_dump() | {
                "event_id": event_id, "episode_id": episode_id,
                "patient_id": episode["patient_id"], "encounter_id": episode["encounter_id"],
                "recorded_at": now, "recorded_by_issuer": principal.issuer,
                "recorded_by_subject": principal.subject,
            }
            await db.emergency_events.insert_one(record, session=session)
            await _audit(db, session, principal, "emergency.event.record", "emergency_event",
                         event_id, payload.tenant_id, payload.facility_id,
                         {"episode_id": episode_id, "event_type": payload.event_type})
    return {"event_id": event_id, "episode_id": episode_id, "recorded_at": now}


@router.post("/episodes/{episode_id}/handovers", status_code=status.HTTP_201_CREATED)
async def create_emergency_handover(episode_id: str, payload: EmergencyHandoverCreate, request: Request,
                                    principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ED_ROLES)
    handover_id, now = str(uuid4()), datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            episode = await _episode(db, payload.tenant_id, payload.facility_id, episode_id, session)
            if episode["status"] != "active":
                raise HTTPException(status_code=409, detail="Emergency episode is not active")
            await _touch_active_episode(db, episode, now, session)
            record = payload.model_dump() | {
                "handover_id": handover_id, "episode_id": episode_id,
                "patient_id": episode["patient_id"], "encounter_id": episode["encounter_id"],
                "status": "awaiting_acknowledgement", "created_at": now,
                "author_issuer": principal.issuer, "author_subject": principal.subject,
            }
            await db.emergency_handovers.insert_one(record, session=session)
            await _audit(db, session, principal, "emergency.handover.create", "emergency_handover",
                         handover_id, payload.tenant_id, payload.facility_id, {"episode_id": episode_id})
    return {"handover_id": handover_id, "status": "awaiting_acknowledgement"}


@router.post("/episodes/{episode_id}/handovers/{handover_id}/acknowledge")
async def acknowledge_emergency_handover(episode_id: str, handover_id: str,
                                         payload: EmergencyHandoverAcknowledge, request: Request,
                                         principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, ED_ROLES)
    now = datetime.now(timezone.utc)
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            await _episode(db, payload.tenant_id, payload.facility_id, episode_id, session)
            handover = await db.emergency_handovers.find_one({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "episode_id": episode_id, "handover_id": handover_id,
                "status": "awaiting_acknowledgement",
            }, session=session)
            if handover is None:
                raise HTTPException(status_code=404, detail="Pending emergency handover not found")
            if handover["author_issuer"] == principal.issuer and handover["author_subject"] == principal.subject:
                raise HTTPException(status_code=403, detail="Handover author cannot acknowledge their own handover")
            changed = await db.emergency_handovers.update_one(
                {"_id": handover["_id"], "status": "awaiting_acknowledgement"},
                {"$set": {"status": "acknowledged", "acknowledgement_note": payload.acknowledgement_note,
                          "acknowledged_at": now, "acknowledger_issuer": principal.issuer,
                          "acknowledger_subject": principal.subject}}, session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Handover state changed; reload before retrying")
            await _audit(db, session, principal, "emergency.handover.acknowledge",
                         "emergency_handover", handover_id, payload.tenant_id,
                         payload.facility_id, {"episode_id": episode_id})
    return {"handover_id": handover_id, "status": "acknowledged", "acknowledged_at": now}


@router.post("/episodes/{episode_id}/disposition")
async def decide_emergency_disposition(episode_id: str, payload: EmergencyDispositionCreate, request: Request,
                                       principal: Principal = Depends(require_principal)):
    db = _db(request)
    await authorize_facility_access(request, principal, payload.tenant_id, payload.facility_id, DISPOSITION_ROLES)
    now = datetime.now(timezone.utc)
    if payload.decided_at > now:
        raise HTTPException(status_code=422, detail="Decision time cannot be in the future")
    if payload.disposition in {"transfer", "refer"} and not payload.destination:
        raise HTTPException(status_code=422, detail="A destination is required for transfer or referral")
    disposition_id = str(uuid4())
    async with await request.app.state.mongo_client.start_session() as session:
        async with session.start_transaction():
            episode = await _episode(db, payload.tenant_id, payload.facility_id, episode_id, session)
            if episode["status"] != "active":
                raise HTTPException(status_code=409, detail="Emergency episode already has a disposition")
            unresolved_handovers = await db.emergency_handovers.count_documents({
                "tenant_id": payload.tenant_id, "facility_id": payload.facility_id,
                "episode_id": episode_id, "status": "awaiting_acknowledgement",
            }, session=session)
            if unresolved_handovers:
                raise HTTPException(status_code=409, detail="Acknowledge or cancel outstanding handovers before disposition")
            record = payload.model_dump() | {
                "disposition_id": disposition_id, "episode_id": episode_id,
                "patient_id": episode["patient_id"], "encounter_id": episode["encounter_id"],
                "recorded_at": now, "decided_by_issuer": principal.issuer,
                "decided_by_subject": principal.subject,
            }
            await db.emergency_dispositions.insert_one(record, session=session)
            changed = await db.emergency_episodes.update_one(
                {"_id": episode["_id"], "status": "active"},
                {"$set": {"status": "disposed", "disposition_id": disposition_id,
                          "disposed_at": now, "disposition": payload.disposition}},
                session=session,
            )
            if changed.modified_count != 1:
                raise HTTPException(status_code=409, detail="Episode state changed; retry after reload")
            await _audit(db, session, principal, "emergency.disposition.decide", "emergency_episode",
                         episode_id, payload.tenant_id, payload.facility_id,
                         {"disposition": payload.disposition, "destination": payload.destination})
    return {"episode_id": episode_id, "disposition_id": disposition_id,
            "status": "disposed", "disposition": payload.disposition}
