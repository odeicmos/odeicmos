import pytest
from pydantic import ValidationError

from odei_api.routers.procurement import (
    GoodsReceiptCreate, PurchaseOrderAction, PurchaseOrderCreate,
    PurchaseOrderLine, SupplierCreate,
)


def test_supplier_requires_scoped_identity_and_legal_name():
    supplier = SupplierCreate(
        tenant_id="tenant-a", facility_id="facility-a",
        supplier_code="SUP-001", legal_name="Uganda Medical Supplies Ltd",
    )
    assert supplier.supplier_code == "SUP-001"
    with pytest.raises(ValidationError):
        SupplierCreate(
            tenant_id="tenant-a", facility_id="facility-a",
            supplier_code="SUP-001", legal_name="X",
        )


def test_purchase_order_lines_use_integer_minor_units():
    line = PurchaseOrderLine(
        item_code="GLOVE-M", item_name="Examination gloves medium",
        quantity=20, unit_cost_minor=1500,
    )
    assert line.quantity * line.unit_cost_minor == 30000
    with pytest.raises(ValidationError):
        PurchaseOrderLine(
            item_code="GLOVE-M", item_name="Examination gloves medium",
            quantity=0, unit_cost_minor=1500,
        )


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


def test_purchase_order_action_rejects_unexpected_fields():
    action = PurchaseOrderAction(tenant_id="tenant-a", facility_id="facility-a")
    assert action.reason is None
    with pytest.raises(ValidationError):
        PurchaseOrderAction(
            tenant_id="tenant-a", facility_id="facility-a", approved=True,
        )


def test_purchase_order_rejects_duplicate_item_codes():
    line = {
        "item_code": "AMOX500", "item_name": "Amoxicillin 500mg",
        "quantity": 10, "unit_cost_minor": 1500,
    }
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(
            tenant_id="tenant-a", facility_id="facility-a", supplier_id="supplier-a",
            currency="UGX", lines=[line, line],
        )
