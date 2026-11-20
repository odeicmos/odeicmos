import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from odei_api.routers.nursing import (
    HandoverAcknowledge, HandoverCreate, NursingTaskCreate, NursingTaskOutcome,
)


def scope(**values):
    return {"tenant_id": "tenant-a", "facility_id": "facility-a", **values}


def test_nursing_task_requires_timezone_and_valid_category():
    task = NursingTaskCreate(**scope(
        patient_id="p1", encounter_id="e1", category="monitoring",
        instruction="Record observations every four hours",
        due_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    ))
    assert task.priority == "routine"
    with pytest.raises(ValidationError):
        NursingTaskCreate(**scope(
            patient_id="p1", encounter_id="e1", category="unknown",
            instruction="Observe patient", due_at=datetime(2027, 1, 1),
        ))


def test_task_outcome_is_constrained_and_rejects_extra_fields():
    result = NursingTaskOutcome(**scope(outcome="completed", outcome_note="Care delivered"))
    assert result.outcome == "completed"
    with pytest.raises(ValidationError):
        NursingTaskOutcome(**scope(outcome="deleted", outcome_note="Care delivered"))


def test_handover_requires_sbar_sections_and_risk_flags():
    handover = HandoverCreate(**scope(
        patient_id="p1", encounter_id="e1", situation="Stable after review",
        background="Admitted overnight", assessment="Pain controlled",
        recommendations="Continue observations", risk_flags=["falls"],
    ))
    assert handover.risk_flags == ["falls"]
    with pytest.raises(ValidationError):
        HandoverCreate(**scope(
            patient_id="p1", encounter_id="e1", situation="x",
            background="b", assessment="a", recommendations="r",
            unexpected="not allowed",
        ))


def test_handover_acknowledgement_requires_note():
    payload = HandoverAcknowledge(**scope(acknowledgement_note="Received and understood"))
    assert "understood" in payload.acknowledgement_note
