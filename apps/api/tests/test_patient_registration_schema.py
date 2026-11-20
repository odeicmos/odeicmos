from datetime import date

import pytest
from pydantic import ValidationError

from odei_api.schemas import PatientRegistrationCreate


def valid_payload(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "facility_id": "facility-a",
        "medical_record_number": "MRN-0001",
        "legal_name": "Test Patient",
        "date_of_birth": date(1990, 1, 1),
        "sex_at_birth": "not_recorded",
    }
    values.update(overrides)
    return values


def test_patient_registration_accepts_minimal_valid_record():
    payload = PatientRegistrationCreate(**valid_payload())
    assert payload.medical_record_number == "MRN-0001"
    assert payload.date_of_birth == date(1990, 1, 1)


def test_patient_registration_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        PatientRegistrationCreate(**valid_payload(diagnosis="untrusted free text"))


def test_patient_registration_rejects_invalid_mrn():
    with pytest.raises(ValidationError):
        PatientRegistrationCreate(**valid_payload(medical_record_number="bad MRN with spaces"))


def test_patient_registration_does_not_require_optional_demographics():
    payload = PatientRegistrationCreate(**valid_payload(date_of_birth=None, phone_number=None))
    assert payload.date_of_birth is None
    assert payload.phone_number is None
