from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from odei_api.routers.referrals import ReferralCompletion, ReferralCreate, ReferralDecision


def scope(**values):
    return {"tenant_id": "tenant-a", "facility_id": "facility-a", **values}


def test_referral_requires_timezone_aware_request_and_supported_urgency():
    payload = ReferralCreate(**scope(
        patient_id="p1", encounter_id="e1", referral_type="external",
        specialty="Cardiology", destination_facility="Regional hospital",
        reason="Needs specialist assessment", clinical_question="Please assess chest pain",
        urgency="urgent", requested_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    ))
    assert payload.urgency == "urgent"
    with pytest.raises(ValidationError):
        ReferralCreate(**scope(
            patient_id="p1", encounter_id="e1", referral_type="external",
            specialty="Cardiology", destination_facility="Hospital",
            reason="Needs review", clinical_question="Please assess",
            urgency="immediate", requested_at=datetime(2026, 11, 20),
        ))


def test_referral_decision_and_completion_are_constrained():
    decision = ReferralDecision(**scope(
        decision="accepted", rationale="Service has capacity",
        planned_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
    ))
    assert decision.decision == "accepted"
    with pytest.raises(ValidationError):
        ReferralDecision(**scope(decision="maybe", rationale="Not a valid decision"))
    completion = ReferralCompletion(**scope(
        outcome="completed", summary="Specialist assessment completed",
        completed_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
    ))
    assert completion.outcome == "completed"
