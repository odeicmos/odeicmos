import pytest
from pydantic import ValidationError

from odei_api.routers.insurance import PayerCreate, EligibilityRecord, ClaimCreate, ClaimDecision


def scope(**overrides):
    values = {"tenant_id": "tenant-a", "facility_id": "facility-a"}
    values.update(overrides)
    return values


def test_payer_requires_code_and_name():
    payer = PayerCreate(**scope(payer_code="NHIF", name="Example payer"))
    assert payer.payer_code == "NHIF"
    with pytest.raises(ValidationError):
        PayerCreate(**scope(payer_code="", name="Example payer"))


def test_eligibility_requires_explicit_status_and_member_identifier():
    record = EligibilityRecord(**scope(patient_id="patient-1", payer_code="NHIF",
        member_number="MEM-1", coverage_status="eligible",
        checked_at="2026-11-19T08:00:00Z"))
    assert record.coverage_status == "eligible"
    with pytest.raises(ValidationError):
        EligibilityRecord(**scope(patient_id="patient-1", payer_code="NHIF",
            member_number="MEM-1", coverage_status="unknown-status",
            checked_at="2026-11-19T08:00:00Z"))


def test_claim_amount_and_currency_are_bounded():
    claim = ClaimCreate(**scope(invoice_id="inv-1", eligibility_id="elig-1",
        claimed_amount_minor=10000, currency="UGX"))
    assert claim.claimed_amount_minor == 10000
    with pytest.raises(ValidationError):
        ClaimCreate(**scope(invoice_id="inv-1", eligibility_id="elig-1",
            claimed_amount_minor=0, currency="UGX"))


def test_claim_decision_requires_valid_status_and_amount():
    decision = ClaimDecision(**scope(decision="accepted", approved_amount_minor=5000,
        reason="Approved by payer"))
    assert decision.decision == "accepted"
    with pytest.raises(ValidationError):
        ClaimDecision(**scope(decision="unknown", approved_amount_minor=0, reason="Rejected"))
