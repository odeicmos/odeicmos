import pytest
from pydantic import ValidationError

from odei_api.routers.accounting import AccountCreate, JournalPost


def journal(**overrides):
    data = {
        "tenant_id": "tenant-a", "facility_id": "facility-a",
        "journal_date": "2026-11-19T10:00:00+03:00", "currency": "UGX",
        "description": "Consultation revenue receipt", "source_type": "payment",
        "source_id": "payment-1", "idempotency_key": "payment-1-journal",
        "lines": [
            {"account_code": "CASH", "debit_minor": 10000},
            {"account_code": "REVENUE", "credit_minor": 10000},
        ],
    }
    data.update(overrides)
    return data


def test_chart_account_rejects_unknown_fields_and_validates_code():
    account = AccountCreate(
        tenant_id="tenant-a", facility_id="facility-a", account_code="CASH-01",
        name="Cash on hand", account_type="asset", normal_balance="debit",
    )
    assert account.account_type == "asset"
    with pytest.raises(ValidationError):
        AccountCreate(
            tenant_id="tenant-a", facility_id="facility-a", account_code="bad code",
            name="Cash on hand", account_type="asset", normal_balance="debit",
        )


def test_journal_requires_balanced_positive_debits_and_credits():
    payload = JournalPost(**journal())
    assert payload.lines[0].debit_minor == payload.lines[1].credit_minor
    with pytest.raises(ValidationError):
        JournalPost(**journal(lines=[
            {"account_code": "CASH", "debit_minor": 10000},
            {"account_code": "REVENUE", "credit_minor": 9000},
        ]))


def test_journal_line_cannot_have_both_or_neither_sides():
    with pytest.raises(ValidationError):
        JournalPost(**journal(lines=[
            {"account_code": "CASH", "debit_minor": 10000, "credit_minor": 10000},
            {"account_code": "REVENUE", "credit_minor": 10000},
        ]))
    with pytest.raises(ValidationError):
        JournalPost(**journal(lines=[
            {"account_code": "CASH"},
            {"account_code": "REVENUE", "credit_minor": 10000},
        ]))


def test_journal_requires_timezone_and_unique_accounts():
    with pytest.raises(ValidationError):
        JournalPost(**journal(journal_date="2026-11-19T10:00:00"))
    with pytest.raises(ValidationError):
        JournalPost(**journal(lines=[
            {"account_code": "CASH", "debit_minor": 5000},
            {"account_code": "CASH", "credit_minor": 5000},
        ]))
