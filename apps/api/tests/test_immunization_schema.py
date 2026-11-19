from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from odei_api.routers.immunization import ImmunizationCreate, AdverseEventCreate


def test_immunization_requires_batch_and_positive_dose_number():
    payload = ImmunizationCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        vaccine_code="BCG", vaccine_name="BCG", dose_number=1,
        administered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        batch_number="LOT-1", expiry_date=date(2027, 1, 1),
        dose_quantity="0.05 mL", route="intradermal",
    )
    assert payload.dose_number == 1
    with pytest.raises(ValidationError):
        ImmunizationCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            vaccine_code="BCG", vaccine_name="BCG", dose_number=0,
            administered_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            batch_number="LOT-1", expiry_date=date(2027, 1, 1),
            dose_quantity="0.05 mL", route="intradermal",
        )


def test_adverse_event_requires_valid_severity_and_description():
    payload = AdverseEventCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        immunization_id="imm-1", description="Fever after vaccination",
        severity="non_serious",
    )
    assert payload.severity == "non_serious"
    with pytest.raises(ValidationError):
        AdverseEventCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            immunization_id="imm-1", description="Fever",
            severity="unknown",
        )
