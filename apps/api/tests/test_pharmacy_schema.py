import pytest
from pydantic import ValidationError

from datetime import datetime, timezone

from odei_api.routers.pharmacy import (
    MedicationLine,
    MedicationOrderCreate,
    _fefo_lot_pipeline,
    _unexpired_lot_filter,
)


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


def test_fefo_filter_accepts_unexpired_and_non_expiring_lots():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    assert _unexpired_lot_filter(now) == {
        "$or": [{"expiry_at": {"$gt": now}}, {"expiry_at": None}]
    }


def test_fefo_pipeline_sorts_non_expiring_lots_after_expiring_lots():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    pipeline = _fefo_lot_pipeline("tenant-a", "facility-a", "AMOX500", now)
    assert pipeline[0]["$match"]["tenant_id"] == "tenant-a"
    assert pipeline[0]["$match"]["facility_id"] == "facility-a"
    assert pipeline[0]["$match"]["$or"] == [
        {"expiry_at": {"$gt": now}}, {"expiry_at": None}
    ]
    assert pipeline[1]["$addFields"]["_fefo_expiry_sort"]["$ifNull"][0] == "$expiry_at"
    assert pipeline[2]["$sort"] == {
        "_fefo_expiry_sort": 1, "received_at": 1, "_id": 1
    }
