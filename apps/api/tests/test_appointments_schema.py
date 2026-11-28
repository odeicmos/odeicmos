import pytest
from pydantic import ValidationError

from odei_api.routers.appointments import (
    AppointmentCreate, AppointmentAction, _practitioner_schedule_lock_id,
)


def scope(**overrides):
    values = {"tenant_id": "tenant-a", "facility_id": "facility-a"}
    values.update(overrides)
    return values


def test_appointment_requires_timezone_and_valid_interval():
    values = scope(patient_id="patient-1", starts_at="2026-11-20T09:00:00Z",
        ends_at="2026-11-20T09:30:00Z", service_code="OPD",
        reason="Follow-up consultation")
    appointment = AppointmentCreate(**values)
    assert appointment.ends_at > appointment.starts_at
    with pytest.raises(ValidationError):
        AppointmentCreate(**(values | {"ends_at": "2026-11-20T08:30:00Z"}))
    with pytest.raises(ValidationError):
        AppointmentCreate(**(values | {"starts_at": "2026-11-20T09:00:00"}))


def test_appointment_action_rejects_unexpected_fields():
    action = AppointmentAction(**scope(reason="Patient requested cancellation"))
    assert action.reason
    with pytest.raises(ValidationError):
        AppointmentAction(**scope(unexpected="not allowed"))


def test_practitioner_schedule_lock_is_stable_and_facility_scoped():
    key = _practitioner_schedule_lock_id("tenant-a", "facility-a", "practitioner-1")
    assert key == _practitioner_schedule_lock_id("tenant-a", "facility-a", "practitioner-1")
    assert key != _practitioner_schedule_lock_id("tenant-a", "facility-b", "practitioner-1")
    assert key != _practitioner_schedule_lock_id("tenant-b", "facility-a", "practitioner-1")
    assert key != _practitioner_schedule_lock_id("tenant-a", "facility-a", "practitioner-2")
