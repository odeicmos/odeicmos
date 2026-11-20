from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from odei_api.routers.emergency import (
    EmergencyDispositionCreate, EmergencyEpisodeCreate, EmergencyEventCreate,
    EmergencyHandoverCreate,
)


def scope(**values):
    return {"tenant_id": "tenant-a", "facility_id": "facility-a", **values}


def test_emergency_episode_requires_timezone_aware_arrival():
    payload = EmergencyEpisodeCreate(**scope(
        encounter_id="enc-1", arrival_mode="ambulance",
        arrival_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        presenting_complaint="Road traffic injury",
    ))
    assert payload.arrival_mode == "ambulance"
    with pytest.raises(ValidationError):
        EmergencyEpisodeCreate(**scope(
            encounter_id="enc-1", arrival_mode="walk_in",
            arrival_at=datetime(2026, 11, 20), presenting_complaint="Fever",
        ))


def test_emergency_event_requires_actions_and_aware_timestamp():
    payload = EmergencyEventCreate(**scope(
        event_type="resuscitation", occurred_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        summary="Resuscitation team activated", actions_taken=["Team called", "Equipment prepared"],
        response="Senior clinician assumed lead",
    ))
    assert len(payload.actions_taken) == 2
    with pytest.raises(ValidationError):
        EmergencyEventCreate(**scope(
            event_type="other", occurred_at=datetime(2026, 11, 20),
            summary="Event", actions_taken=[], response="No response",
        ))


def test_emergency_disposition_requires_destination_for_transfer():
    base = scope(
        disposition="transfer", rationale="Requires higher level of care",
        decided_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    )
    incomplete = EmergencyDispositionCreate(**base)
    assert incomplete.destination is None
    payload = EmergencyDispositionCreate(**(base | {"destination": "Regional referral hospital"}))
    assert payload.disposition == "transfer"
    assert payload.destination == "Regional referral hospital"


def test_emergency_handover_is_bounded_and_rejects_extra_fields():
    payload = EmergencyHandoverCreate(**scope(
        receiving_service="Medical ward", clinical_summary="Patient reviewed and stable",
        outstanding_actions=["Repeat observations"], risk_flags=["falls"],
    ))
    assert payload.receiving_service == "Medical ward"
    with pytest.raises(ValidationError):
        EmergencyHandoverCreate(**scope(
            receiving_service="Ward", clinical_summary="Summary", unapproved="extra",
        ))
