import pytest
from pydantic import ValidationError

from odei_api.routers.patients import PatientMatchReview


def test_identity_review_requires_distinct_records_and_reason():
    review = PatientMatchReview(
        tenant_id="tenant-a", facility_id="facility-a",
        patient_id="patient-a", candidate_patient_id="patient-b",
        outcome="needs_more_information",
        rationale="The date of birth is inconsistent and identity evidence is incomplete.",
    )
    assert review.outcome == "needs_more_information"
    with pytest.raises(ValidationError):
        PatientMatchReview(
            tenant_id="tenant-a", facility_id="facility-a",
            patient_id="patient-a", candidate_patient_id="patient-b",
            outcome="merge", rationale="short",
        )
