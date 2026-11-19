import pytest
from pydantic import ValidationError

from odei_api.routers.pharmacy import MedicationAdministrationCreate


def base(**overrides):
    data = {
        "tenant_id": "tenant-a", "facility_id": "facility-a",
        "order_id": "order-a", "medication_code": "AMOX500",
        "action": "administered", "administered_dose": "500 mg",
        "route": "oral", "quantity": 1, "idempotency_key": "dose-20261119-001",
    }
    data.update(overrides)
    return data


def test_administered_dose_requires_route_dose_and_positive_quantity():
    payload = MedicationAdministrationCreate(**base())
    assert payload.action == "administered"
    with pytest.raises(ValidationError):
        MedicationAdministrationCreate(**base(quantity=0))
    with pytest.raises(ValidationError):
        MedicationAdministrationCreate(**base(route=None))


def test_withheld_or_refused_requires_reason_and_zero_quantity():
    payload = MedicationAdministrationCreate(**base(
        action="withheld", administered_dose=None, route=None, quantity=0,
        reason="Patient declined",
    ))
    assert payload.action == "withheld"
    with pytest.raises(ValidationError):
        MedicationAdministrationCreate(**base(
            action="refused", administered_dose=None, route=None,
            quantity=1, reason="Patient declined",
        ))


def test_administration_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        MedicationAdministrationCreate(**base(unreviewed_override=True))
