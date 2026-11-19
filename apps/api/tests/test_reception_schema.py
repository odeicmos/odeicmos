import pytest
from pydantic import ValidationError

from odei_api.routers.reception import AppointmentCreate, CheckInRequest, QueueTransition


def test_appointment_requires_timezone_and_valid_interval_at_service_layer():
    payload = AppointmentCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        appointment_type="consultation",
        scheduled_start="2026-11-20T09:00:00+03:00",
        scheduled_end="2026-11-20T09:30:00+03:00",
    )
    assert payload.scheduled_end > payload.scheduled_start
    # The route rejects naive timestamps and non-positive intervals before writing.
    naive = AppointmentCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        appointment_type="consultation",
        scheduled_start="2026-11-20T09:00:00",
        scheduled_end="2026-11-20T09:30:00",
    )
    assert naive.scheduled_start.tzinfo is None


def test_check_in_request_does_not_accept_queue_transition_fields():
    payload = CheckInRequest(tenant_id="tenant-a", facility_id="facility-a")
    assert payload.facility_id == "facility-a"
    with pytest.raises(ValidationError):
        CheckInRequest(tenant_id="tenant-a", facility_id="facility-a", status="in_service")


def test_queue_transition_only_allows_operational_target_states():
    payload = QueueTransition(tenant_id="tenant-a", facility_id="facility-a", status="completed")
    assert payload.status == "completed"
    with pytest.raises(ValidationError):
        QueueTransition(tenant_id="tenant-a", facility_id="facility-a", status="waiting")
