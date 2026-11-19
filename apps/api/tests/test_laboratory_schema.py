import pytest
from pydantic import ValidationError

from odei_api.routers.laboratory import LabOrderCreate, SpecimenCollect, LabResultCreate


def base(**overrides):
    data = {
        "tenant_id": "tenant-a", "facility_id": "facility-a",
        "patient_id": "patient-1", "encounter_id": "encounter-1",
    }
    data.update(overrides)
    return data


def test_lab_order_requires_tests_and_rejects_unknown_fields():
    payload = LabOrderCreate(**base(tests=["CBC", "malaria_rdt"]))
    assert payload.priority == "routine"
    with pytest.raises(ValidationError):
        LabOrderCreate(**base(tests=[]))
    with pytest.raises(ValidationError):
        LabOrderCreate(**base(tests=["CBC"], hidden_field="x"))


def test_specimen_requires_type():
    payload = SpecimenCollect(
        tenant_id="tenant-a", facility_id="facility-a", specimen_type="whole blood"
    )
    assert payload.specimen_type == "whole blood"
    with pytest.raises(ValidationError):
        SpecimenCollect(tenant_id="tenant-a", facility_id="facility-a", specimen_type="x")


def test_result_requires_analyte_and_value():
    payload = LabResultCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        analyte_code="HB", analyte_name="Haemoglobin", value="12.4",
        unit="g/dL", interpretation="normal",
    )
    assert payload.value == "12.4"
    with pytest.raises(ValidationError):
        LabResultCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            analyte_code="HB", analyte_name="Haemoglobin", value="",
        )
