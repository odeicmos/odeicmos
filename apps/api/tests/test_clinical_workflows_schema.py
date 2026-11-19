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

 

def test_triage_vitals_are_bounded_and_acuity_is_required():
    from odei_api.routers.clinical import TriageCreate
    payload = TriageCreate(**scope(encounter_id="enc-1", acuity=2,
        presenting_concern="Chest discomfort", pulse_bpm=88, oxygen_saturation_pct=98))
    assert payload.acuity == 2
    with pytest.raises(ValidationError):
        TriageCreate(**scope(encounter_id="enc-1", acuity=6, presenting_concern="Concern"))


def test_observation_and_diagnosis_schema_validation():
    from odei_api.routers.clinical import ObservationCreate, DiagnosisCreate
    observation = ObservationCreate(**scope(encounter_id="enc-1", code="8867-4",
        display="Heart rate", value=72, unit="/min"))
    assert observation.value == 72
    diagnosis = DiagnosisCreate(**scope(encounter_id="enc-1",
        code_system="http://snomed.info/sct", code="123", display="Example diagnosis"))
    assert diagnosis.clinical_status == "active"
    with pytest.raises(ValidationError):
        DiagnosisCreate(**scope(encounter_id="enc-1", code_system="snomed",
            code="1", display="Example", unexpected="bad"))
