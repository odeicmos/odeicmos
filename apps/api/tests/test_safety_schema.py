import pytest
from pydantic import ValidationError

from odei_api.routers.safety import IncidentCreate, IncidentClose, InvestigationNote


def test_incident_report_requires_category_severity_and_timezone():
    report = IncidentCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        category="near_miss", severity="near_miss",
        occurred_at="2026-11-20T10:00:00+03:00",
        location_code="OPD-01",
        summary="Patient almost received a medication intended for another patient.",
    )
    assert report.confidential is True
    with pytest.raises(ValidationError):
        IncidentCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            category="near_miss", severity="unknown",
            occurred_at="2026-11-20T10:00:00+03:00",
            location_code="OPD-01", summary="A sufficiently detailed safety report.",
        )


def test_investigation_notes_are_typed_and_require_detail():
    note = InvestigationNote(
        tenant_id="tenant-a", facility_id="facility-a",
        note_type="corrective_action",
        note="Two-person verification step added to the medication handoff process.",
    )
    assert note.note_type == "corrective_action"
    with pytest.raises(ValidationError):
        InvestigationNote(
            tenant_id="tenant-a", facility_id="facility-a",
            note_type="other", note="x",
        )


def test_incident_closure_requires_root_cause_and_evidence():
    close = IncidentClose(
        tenant_id="tenant-a", facility_id="facility-a",
        root_cause_summary="The handoff checklist did not include a patient identifier read-back.",
        corrective_action_summary="A two-identifier read-back and monthly audit were introduced.",
        residual_risk="low", evidence_reference="private-object://closure-evidence",
    )
    assert close.residual_risk == "low"
    with pytest.raises(ValidationError):
        IncidentClose(
            tenant_id="tenant-a", facility_id="facility-a",
            root_cause_summary="short", corrective_action_summary="short",
            residual_risk="low", evidence_reference="x",
        )
