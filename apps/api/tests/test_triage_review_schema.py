import pytest
from pydantic import ValidationError

from odei_api.routers.clinical import TriageReviewCreate


def test_triage_review_requires_human_disposition_and_rationale():
    payload = TriageReviewCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        reviewed_acuity=2, disposition="emergency_response",
        rationale="Clinician review identifies immediate escalation need.",
    )
    assert payload.disposition == "emergency_response"
    with pytest.raises(ValidationError):
        TriageReviewCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            reviewed_acuity=2, disposition="urgent_review", rationale="no",
        )


def test_acuity_override_requires_reason_at_workflow_layer():
    payload = TriageReviewCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        reviewed_acuity=4, disposition="routine_queue",
        rationale="Reviewed against approved facility protocol.",
        override_reason="Reassessment after repeat observations.",
    )
    assert payload.override_reason
    with pytest.raises(ValidationError):
        TriageReviewCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            reviewed_acuity=0, disposition="routine_queue",
            rationale="Valid rationale.",
        )
