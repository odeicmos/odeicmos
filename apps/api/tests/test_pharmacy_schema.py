import pytest
from pydantic import ValidationError

from odei_api.routers.pharmacy import MedicationLine, MedicationOrderCreate


def test_medication_line_requires_positive_bounded_quantity():
    line = MedicationLine(
        medication_code="AMOX500", display_name="Amoxicillin 500 mg",
        dose="500 mg", route="oral", frequency="three times daily",
        quantity=21,
    )
    assert line.quantity == 21
    with pytest.raises(ValidationError):
        MedicationLine(
            medication_code="AMOX500", display_name="Amoxicillin 500 mg",
            dose="500 mg", route="oral", frequency="three times daily",
            quantity=0,
        )


def test_medication_order_requires_at_least_one_line_and_rejects_extra_fields():
    values = {
        "tenant_id": "tenant-a", "facility_id": "facility-a",
        "patient_id": "patient-1", "encounter_id": "encounter-1",
        "lines": [{
            "medication_code": "AMOX500", "display_name": "Amoxicillin 500 mg",
            "dose": "500 mg", "route": "oral", "frequency": "three times daily",
            "quantity": 21,
        }],
    }
    assert MedicationOrderCreate(**values).lines[0].medication_code == "AMOX500"
    with pytest.raises(ValidationError):
        MedicationOrderCreate(**(values | {"lines": []}))
    with pytest.raises(ValidationError):
        MedicationOrderCreate(**(values | {"unexpected": "field"}))
