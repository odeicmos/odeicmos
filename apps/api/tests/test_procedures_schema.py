from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from odei_api.routers.procedures import (
    ProcedureCompletion, ProcedureRequest, ProcedureSafetyChecklist, ProcedureStart,
)


def scope(**values):
    return {"tenant_id": "tenant-a", "facility_id": "facility-a", **values}


def test_procedure_request_requires_aware_schedule_and_bounded_fields():
    payload = ProcedureRequest(**scope(
        patient_id="p1", encounter_id="e1", procedure_code="PROC-1",
        procedure_name="Wound closure", indication="Laceration repair",
        laterality="left", planned_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
    ))
    assert payload.requires_consent is True
    with pytest.raises(ValidationError):
        ProcedureRequest(**scope(
            patient_id="p1", encounter_id="e1", procedure_code="PROC-1",
            procedure_name="Wound closure", indication="Repair",
            planned_at=datetime(2026, 12, 1),
        ))


def test_procedure_checklist_and_start_require_explicit_safety_fields():
    checklist = ProcedureSafetyChecklist(**scope(
        patient_identity_verified=True, procedure_and_site_confirmed=True,
        consent_status="obtained", allergies_reviewed=True,
        equipment_and_supplies_checked=True, infection_prevention_ready=True,
        site_marking_status="completed", checklist_note="All checks complete",
    ))
    assert checklist.consent_status == "obtained"
    with pytest.raises(ValidationError):
        ProcedureStart(**scope(time_out_confirmed=False, team_members=[], start_note="No time-out"))


def test_procedure_completion_requires_timezone_and_outcome():
    payload = ProcedureCompletion(**scope(
        outcome="completed", performed_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        findings="Wound closed", complications="None observed",
        post_procedure_plan="Review wound in 48 hours",
    ))
    assert payload.outcome == "completed"
    with pytest.raises(ValidationError):
        ProcedureCompletion(**scope(
            outcome="unknown", performed_at=datetime(2026, 11, 20),
            findings="Done", complications="None", post_procedure_plan="Review",
        ))
