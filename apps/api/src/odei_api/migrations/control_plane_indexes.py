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
    await db.lab_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("order_id", ASCENDING)],
        unique=True, name="uq_lab_order_scope_id",
    )
    await db.lab_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_lab_order_patient_time",
    )
    await db.specimens.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("specimen_id", ASCENDING)],
        unique=True, name="uq_specimen_scope_id",
    )
    await db.specimens.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("order_id", ASCENDING)],
        unique=True, name="uq_specimen_order",
    )
    await db.lab_results.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("result_id", ASCENDING)],
        unique=True, name="uq_lab_result_scope_id",
    )
    await db.lab_results.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("order_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="ix_lab_result_order_time",
    )
    await db.immunizations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("immunization_id", ASCENDING)],
        unique=True, name="uq_immunization_scope_id",
    )
    await db.immunizations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("administered_at", DESCENDING)],
        name="ix_immunization_patient_time",
    )
    await db.immunization_adverse_events.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("adverse_event_id", ASCENDING)],
        unique=True, name="uq_immunization_ae_scope_id",
    )
    await db.invoices.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("invoice_id", ASCENDING)],
        unique=True, name="uq_invoice_scope_id",
    )
    await db.invoices.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_invoice_patient_time",
    )
    await db.payments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("payment_id", ASCENDING)],
        unique=True, name="uq_payment_scope_id",
    )
    await db.cash_sessions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("cash_session_id", ASCENDING)],
        unique=True, name="uq_cash_session_scope_id",
    )
    await db.cash_sessions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("opened_by_subject", ASCENDING), ("status", ASCENDING)],
        name="ix_cash_session_operator_status",
    )
    await db.purchase_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("purchase_order_id", ASCENDING)],
        unique=True, name="uq_purchase_order_scope_id",
    )
    await db.goods_receipts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("receipt_id", ASCENDING)],
        unique=True, name="uq_goods_receipt_scope_id",
    )
    await db.goods_receipts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("purchase_order_id", ASCENDING), ("item_code", ASCENDING)],
        name="ix_goods_receipt_order_item",
    )
    await db.inventory_lots.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("item_code", ASCENDING), ("lot_number", ASCENDING)],
        unique=True, name="uq_inventory_lot_item_number",
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

    await db.triage_assessments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("triage_id", ASCENDING)],
        unique=True, name="uq_triage_assessment_scope_id",
    )
    await db.triage_assessments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("encounter_id", ASCENDING), ("recorded_at", DESCENDING)],
        name="ix_triage_encounter_time",
    )
    await db.observations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("observation_id", ASCENDING)],
        unique=True, name="uq_observation_scope_id",
    )
    await db.observations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("effective_at", DESCENDING)],
        name="ix_observation_patient_time",
    )
    await db.diagnoses.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("diagnosis_id", ASCENDING)],
        unique=True, name="uq_diagnosis_scope_id",
    )
    await db.diagnoses.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("encounter_id", ASCENDING), ("clinical_status", ASCENDING)],
        name="ix_diagnosis_encounter_status",
    )

    await db.beds.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("bed_id", ASCENDING)],
        unique=True, name="uq_bed_scope_id",
    )
    await db.beds.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("bed_code", ASCENDING)],
        unique=True, name="uq_bed_facility_code",
    )
    await db.beds.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("ward_code", ASCENDING), ("status", ASCENDING)],
        name="ix_bed_ward_status",
    )
    await db.admissions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("admission_id", ASCENDING)],
        unique=True, name="uq_admission_scope_id",
    )
    await db.admissions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("status", ASCENDING)],
        name="ix_admission_patient_status",
    )
    await db.admission_transfers.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("transfer_id", ASCENDING)],
        unique=True, name="uq_admission_transfer_scope_id",
    )

    await db.payers.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("payer_id", ASCENDING)],
        unique=True, name="uq_payer_scope_id",
    )
    await db.payers.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("payer_code", ASCENDING)],
        unique=True, name="uq_payer_facility_code",
    )
    await db.insurance_eligibility.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("eligibility_id", ASCENDING)],
        unique=True, name="uq_insurance_eligibility_scope_id",
    )
    await db.insurance_eligibility.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("checked_at", DESCENDING)],
        name="ix_insurance_eligibility_patient_time",
    )
    await db.insurance_claims.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("claim_id", ASCENDING)],
        unique=True, name="uq_insurance_claim_scope_id",
    )
    await db.insurance_claims.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("invoice_id", ASCENDING), ("status", ASCENDING)],
        name="ix_insurance_claim_invoice_status",
    )
