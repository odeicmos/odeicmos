from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from odei_api.routers.clinical import EncounterCreate, ClinicalNoteCreate, CarePlanCreate


def scope(**overrides):
    values = {"tenant_id": "tenant-a", "facility_id": "facility-a"}
    values.update(overrides)
    return values


def test_encounter_requires_supported_type_and_rejects_extra_fields():
    payload = EncounterCreate(**scope(patient_id="patient-1", encounter_type="opd"))
    assert payload.priority == "routine"
    with pytest.raises(ValidationError):
        EncounterCreate(**scope(patient_id="patient-1", encounter_type="unknown"))
    with pytest.raises(ValidationError):
        EncounterCreate(**scope(patient_id="patient-1", encounter_type="opd", diagnosis="x"))


def test_clinical_note_requires_bounded_nonempty_body():
    payload = ClinicalNoteCreate(**scope(
        encounter_id="enc-1", note_type="assessment", body="Assessment documented."
    ))
    assert payload.note_type == "assessment"
    with pytest.raises(ValidationError):
        ClinicalNoteCreate(**scope(encounter_id="enc-1", note_type="assessment", body=""))


def test_care_plan_requires_goals_and_interventions():
    payload = CarePlanCreate(**scope(
        patient_id="patient-1", title="Hypertension follow-up",
        goals=["Improve blood pressure control"],
        interventions=["Review blood pressure at next visit"],
        review_due_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
    ))
    assert len(payload.goals) == 1
    with pytest.raises(ValidationError):
        CarePlanCreate(**scope(
            patient_id="patient-1", title="Plan", goals=[],
            interventions=["Follow up"],
        ))
