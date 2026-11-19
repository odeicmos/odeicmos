import pytest
from pydantic import ValidationError

from odei_api.routers.inpatient import BedCreate, AdmissionCreate, BedTransfer, DischargeCreate


def scope(**overrides):
    values = {"tenant_id": "tenant-a", "facility_id": "facility-a"}
    values.update(overrides)
    return values


def test_bed_requires_unique_scoped_identifier_fields_and_valid_type():
    bed = BedCreate(**scope(ward_code="ward-a", ward_name="Medical",
                            bed_code="M-01", bed_type="general"))
    assert bed.bed_type == "general"
    with pytest.raises(ValidationError):
        BedCreate(**scope(ward_code="ward-a", ward_name="Medical",
                          bed_code="M-01", bed_type="unknown"))


def test_admission_requires_patient_encounter_bed_and_reason():
    admission = AdmissionCreate(**scope(patient_id="patient-1",
        encounter_id="enc-1", bed_code="M-01", admission_reason="Observation"))
    assert admission.patient_id == "patient-1"
    with pytest.raises(ValidationError):
        AdmissionCreate(**scope(patient_id="patient-1", encounter_id="enc-1",
                                 bed_code="M-01", admission_reason=""))


def test_transfer_and_discharge_require_reasons_and_valid_disposition():
    transfer = BedTransfer(**scope(destination_bed_code="M-02", reason="Higher observation need"))
    assert transfer.destination_bed_code == "M-02"
    discharge = DischargeCreate(**scope(discharge_disposition="home",
                                        summary="Discharged with follow-up advice"))
    assert discharge.discharge_disposition == "home"
    with pytest.raises(ValidationError):
        DischargeCreate(**scope(discharge_disposition="unknown", summary="A summary"))
