import pytest
from pydantic import ValidationError

from odei_api.routers.workforce import (
    CredentialCreate, CredentialDecision, StaffCreate, StaffDeactivation,
)


def test_staff_registry_requires_minimal_employment_fields():
    staff = StaffCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        staff_code="NUR-001", display_name="Example Nurse",
        employment_type="permanent", start_date="2026-01-01",
    )
    assert staff.employment_type == "permanent"
    with pytest.raises(ValidationError):
        StaffCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            staff_code="NUR-001", display_name="X",
            employment_type="permanent", start_date="2026-01-01",
        )


def test_credential_submission_requires_authority_registration_and_evidence_ref():
    credential = CredentialCreate(
        tenant_id="tenant-a", facility_id="facility-a", staff_id="staff-a",
        profession="Nurse", registration_authority="Nursing Council",
        registration_number="REG-123", evidence_object_ref="private-object-123",
    )
    assert credential.registration_number == "REG-123"
    with pytest.raises(ValidationError):
        CredentialCreate(
            tenant_id="tenant-a", facility_id="facility-a", staff_id="staff-a",
            profession="Nurse", registration_authority="Nursing Council",
            registration_number="",
        )


def test_credential_decision_requires_explicit_reason():
    decision = CredentialDecision(
        tenant_id="tenant-a", facility_id="facility-a",
        decision="verified", rationale="Verified against issuing authority.",
    )
    assert decision.decision == "verified"
    with pytest.raises(ValidationError):
        CredentialDecision(
            tenant_id="tenant-a", facility_id="facility-a",
            decision="verified", rationale="no",
        )


def test_staff_deactivation_has_dedicated_schema():
    payload = StaffDeactivation(
        tenant_id="tenant-a", facility_id="facility-a",
        rationale="Employment ended following approved HR process.",
    )
    assert payload.rationale.startswith("Employment")
    with pytest.raises(ValidationError):
        StaffDeactivation(
            tenant_id="tenant-a", facility_id="facility-a",
            rationale="x", unexpected="field",
        )


def test_shift_schema_rejects_unknown_fields_and_requires_timezone_at_service_layer():
    from odei_api.routers.workforce import ShiftCreate, ShiftAction
    shift = ShiftCreate(
        tenant_id="tenant-a", facility_id="facility-a", staff_id="staff-a",
        department_code="OPD", shift_type="day",
        starts_at="2026-11-20T08:00:00+03:00",
        ends_at="2026-11-20T17:00:00+03:00",
    )
    assert shift.ends_at > shift.starts_at
    action = ShiftAction(
        tenant_id="tenant-a", facility_id="facility-a",
        reason="Staff member is unavailable.",
    )
    assert action.reason
    with pytest.raises(ValidationError):
        ShiftAction(
            tenant_id="tenant-a", facility_id="facility-a",
            reason="x", extra_field="no",
        )
