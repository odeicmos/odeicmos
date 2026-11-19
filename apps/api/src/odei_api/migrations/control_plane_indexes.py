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
    await db.patients.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("medical_record_number", ASCENDING)],
        unique=True, name="uq_patient_facility_mrn",
    )
    await db.patients.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_patient_facility_created",
    )
    await db.encounters.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("encounter_id", ASCENDING)],
        unique=True, name="uq_encounter_scope_id",
    )
    await db.encounters.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("started_at", DESCENDING)],
        name="ix_encounter_patient_timeline",
    )
    await db.clinical_notes.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("note_id", ASCENDING)],
        unique=True, name="uq_clinical_note_scope_id",
    )
    await db.clinical_notes.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("encounter_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_clinical_note_encounter_time",
    )
    await db.care_plans.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("care_plan_id", ASCENDING)],
        unique=True, name="uq_care_plan_scope_id",
    )
    await db.care_plans.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("status", ASCENDING)],
        name="ix_care_plan_patient_status",
    )
    await db.medication_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("order_id", ASCENDING)],
        unique=True, name="uq_medication_order_scope_id",
    )
    await db.medication_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_medication_order_patient_time",
    )
    await db.inventory_lots.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("medication_code", ASCENDING), ("status", ASCENDING), ("expiry_at", ASCENDING)],
        name="ix_inventory_lot_fefo",
    )
    await db.dispensing_events.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("dispense_id", ASCENDING)],
        unique=True, name="uq_dispensing_event_scope_id",
    )
    await db.dispensing_events.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("order_id", ASCENDING)],
        unique=True, name="uq_dispensing_event_order",
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
