import pytest
from pydantic import ValidationError

from odei_api.routers.procurement import PurchaseOrderCreate, GoodsReceiptCreate


def test_purchase_order_requires_positive_quantities_and_currency():
    payload = PurchaseOrderCreate(
        tenant_id="tenant-a", facility_id="facility-a", supplier_id="supplier-a",
        currency="UGX", lines=[{
            "item_code": "AMOX500", "item_name": "Amoxicillin 500mg",
            "quantity": 20, "unit_cost_minor": 1500,
        }],
    )
    assert payload.lines[0].quantity * payload.lines[0].unit_cost_minor == 30000
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(
            tenant_id="tenant-a", facility_id="facility-a", supplier_id="supplier-a",
            currency="ugx", lines=[{
                "item_code": "AMOX500", "item_name": "Amoxicillin 500mg",
                "quantity": 0, "unit_cost_minor": 1500,
            }],
        )


def test_goods_receipt_rejects_zero_quantity_and_unknown_fields():
    with pytest.raises(ValidationError):
        GoodsReceiptCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            purchase_order_id="po-a", item_code="AMOX500",
            quantity_received=0, lot_number="LOT-1", unit_cost_minor=1500,
            unexpected="not-allowed",
        )
