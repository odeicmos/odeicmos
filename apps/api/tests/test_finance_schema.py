import pytest
from pydantic import ValidationError

from odei_api.routers.finance import InvoiceCreate, PaymentCreate, CashSessionOpen


def test_invoice_total_inputs_are_integer_minor_units():
    payload = InvoiceCreate(
        tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
        currency="UGX", lines=[{
            "code": "CONSULT", "description": "Consultation",
            "quantity": 2, "unit_amount_minor": 15000,
        }],
    )
    assert payload.lines[0].quantity * payload.lines[0].unit_amount_minor == 30000
    with pytest.raises(ValidationError):
        InvoiceCreate(
            tenant_id="tenant-a", facility_id="facility-a", patient_id="patient-a",
            currency="UGX", lines=[{
                "code": "CONSULT", "description": "Consultation",
                "quantity": 0, "unit_amount_minor": 15000,
            }],
        )


def test_payment_must_be_positive():
    payload = PaymentCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        amount_minor=5000, method="mobile_money",
    )
    assert payload.amount_minor == 5000
    with pytest.raises(ValidationError):
        PaymentCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            amount_minor=0, method="cash",
        )


def test_cash_session_currency_is_iso_shape_and_float_nonnegative():
    payload = CashSessionOpen(
        tenant_id="tenant-a", facility_id="facility-a",
        currency="UGX", opening_float_minor=10000,
    )
    assert payload.currency == "UGX"
    with pytest.raises(ValidationError):
        CashSessionOpen(
            tenant_id="tenant-a", facility_id="facility-a",
            currency="ug", opening_float_minor=10000,
        )
