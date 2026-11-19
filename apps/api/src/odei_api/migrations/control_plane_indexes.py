"""Versioned MongoDB indexes for ODEI control-plane collections."""
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase


async def apply_control_plane_indexes(db: AsyncDatabase) -> None:
    await db.tenants.create_index([("tenant_id", ASCENDING)], unique=True, name="uq_tenant_id")
    await db.organizations.create_index(
        [("tenant_id", ASCENDING), ("organization_id", ASCENDING)],
        unique=True, name="uq_tenant_organization",
    )
    await db.facilities.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING)],
        unique=True, name="uq_tenant_facility",
    )
    await db.facilities.create_index(
        [("tenant_id", ASCENDING), ("organization_id", ASCENDING), ("status", ASCENDING)],
        name="ix_facility_org_status",
    )
    await db.country_profile_versions.create_index(
        [("country_code", ASCENDING), ("profile_code", ASCENDING), ("version", DESCENDING)],
        unique=True, name="uq_country_profile_version",
    )
    await db.users.create_index(
        [("issuer", ASCENDING), ("subject", ASCENDING)], unique=True, name="uq_oidc_subject"
    )
    await db.role_assignments.create_index(
        [("tenant_id", ASCENDING), ("user_issuer", ASCENDING), ("user_id", ASCENDING), ("facility_id", ASCENDING), ("role", ASCENDING)],
        unique=True, name="uq_scoped_role_assignment",
    )
    await db.audit_events.create_index(
        [("tenant_id", ASCENDING), ("occurred_at", DESCENDING)], name="ix_audit_tenant_time"
    )
    await db.audit_events.create_index(
        [("event_id", ASCENDING)], unique=True, name="uq_audit_event_id"
    )
    await db.configuration_versions.create_index(
        [("scope_type", ASCENDING), ("scope_id", ASCENDING), ("version", DESCENDING)],
        unique=True, name="uq_config_scope_version",
    )
