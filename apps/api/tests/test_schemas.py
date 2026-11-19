import pytest
from pydantic import ValidationError
from odei_api.schemas import TenantCreate, OrganizationCreate, FacilityCreate, RoleAssignmentCreate


def test_tenant_schema_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        TenantCreate(
            tenant_id="tenant_a", name="Example", deployment_model="dedicated",
            country_code="UG", password="not-allowed",
        )


def test_country_code_must_be_uppercase_iso_style_code():
    with pytest.raises(ValidationError):
        OrganizationCreate(
            tenant_id="tenant_a", organization_id="org_a", name="Example",
            country_code="ug",
        )


def test_facility_type_is_constrained():
    with pytest.raises(ValidationError):
        FacilityCreate(
            tenant_id="tenant_a", organization_id="org_a", facility_id="fac_a",
            name="Example", facility_type="unlicensed-service", country_code="UG",
        )


def test_role_assignment_rejects_unknown_role():
    with pytest.raises(ValidationError):
        RoleAssignmentCreate(
            tenant_id="tenant_a", facility_id="fac_a", user_id="user-123",
            role="superuser",
        )
