import pytest
from pydantic import ValidationError

from odei_api.routers.facility_ops import (
    AssetCreate, AssetRelease, WorkOrderCompletion, WorkOrderCreate,
)


def test_asset_register_requires_risk_class_and_location():
    asset = AssetCreate(
        tenant_id="tenant-a", facility_id="facility-a", asset_code="MON-001",
        name="Patient monitor", category="medical_device", location_code="ER-01",
        risk_class="critical", requires_calibration=True,
    )
    assert asset.risk_class == "critical"
    with pytest.raises(ValidationError):
        AssetCreate(
            tenant_id="tenant-a", facility_id="facility-a", asset_code="MON-001",
            name="Patient monitor", category="medical_device", location_code="ER-01",
            risk_class="unrated",
        )


def test_critical_work_order_requires_service_impact():
    order = WorkOrderCreate(
        tenant_id="tenant-a", facility_id="facility-a", asset_id="asset-1",
        issue_summary="Monitor fails self-test at startup.",
        priority="critical", service_impact="out_of_service",
    )
    assert order.priority == "critical"
    with pytest.raises(ValidationError):
        WorkOrderCreate(
            tenant_id="tenant-a", facility_id="facility-a", asset_id="asset-1",
            issue_summary="Monitor fails self-test at startup.",
            priority="invalid", service_impact="none",
        )


def test_maintenance_completion_and_independent_release_require_evidence():
    completion = WorkOrderCompletion(
        tenant_id="tenant-a", facility_id="facility-a",
        work_performed="Replaced power module and completed electrical safety test.",
    )
    release = AssetRelease(
        tenant_id="tenant-a", facility_id="facility-a",
        release_checklist_reference="private-object://checklist-123",
        rationale="Independent inspection confirms safe return to service.",
    )
    assert completion.work_performed
    assert release.release_checklist_reference
    with pytest.raises(ValidationError):
        AssetRelease(
            tenant_id="tenant-a", facility_id="facility-a",
            release_checklist_reference="x", rationale="ok",
        )
