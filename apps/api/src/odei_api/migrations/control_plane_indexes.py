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

    await db.inventory_movements.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("movement_id", ASCENDING)],
        unique=True, name="uq_inventory_movement_scope_id",
    )
    await db.inventory_movements.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("lot_id", ASCENDING), ("occurred_at", ASCENDING)],
        name="ix_inventory_movement_lot_time",
    )
    await db.inventory_movements.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("item_code", ASCENDING), ("occurred_at", DESCENDING)],
        name="ix_inventory_movement_item_time",
    )

    await db.admissions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING)],
        unique=True, partialFilterExpression={"status": "admitted"},
        name="uq_one_active_admission_per_patient",
    )


    await db.chart_of_accounts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("account_code", ASCENDING)],
        unique=True, name="uq_chart_account_facility_code",
    )
    await db.chart_of_accounts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("account_type", ASCENDING), ("status", ASCENDING)],
        name="ix_chart_account_type_status",
    )
    await db.journal_entries.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("journal_id", ASCENDING)],
        unique=True, name="uq_journal_scope_id",
    )
    await db.journal_entries.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True, name="uq_journal_idempotency",
    )
    await db.journal_entries.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("journal_date", DESCENDING)],
        name="ix_journal_facility_date",
    )


    await db.medication_administrations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("administration_id", ASCENDING)],
        unique=True, name="uq_medication_administration_scope_id",
    )
    await db.medication_administrations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("idempotency_key", ASCENDING)],
        unique=True, name="uq_medication_administration_idempotency",
    )
    await db.medication_administrations.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("occurred_at", DESCENDING)],
        name="ix_medication_administration_patient_time",
    )

    await db.appointments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("appointment_id", ASCENDING)],
        unique=True, name="uq_appointment_scope_id",
    )
    await db.appointments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("starts_at", DESCENDING)],
        name="ix_appointment_patient_time",
    )
    await db.appointments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("practitioner_subject", ASCENDING), ("starts_at", ASCENDING), ("ends_at", ASCENDING)],
        name="ix_appointment_practitioner_time",
    )


    await db.cash_sessions.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("opened_by_subject", ASCENDING)],
        unique=True, partialFilterExpression={"status": "open"},
        name="uq_one_open_cash_session_per_operator",
    )


    await db.suppliers.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("supplier_id", ASCENDING)],
        unique=True, name="uq_supplier_scope_id",
    )
    await db.suppliers.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("supplier_code", ASCENDING)],
        unique=True, name="uq_supplier_facility_code",
    )
    await db.purchase_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
        name="ix_purchase_order_status_time",
    )


    await db.clinical_note_amendments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("amendment_id", ASCENDING)],
        unique=True, name="uq_clinical_note_amendment_scope_id",
    )
    await db.clinical_note_amendments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("note_id", ASCENDING), ("version", ASCENDING)],
        unique=True, name="uq_clinical_note_amendment_version",
    )

    await db.triage_assessments.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("review_status", ASCENDING), ("recorded_at", ASCENDING)],
        name="ix_triage_review_status",
    )

    await db.staff_members.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("staff_id", ASCENDING)],
        unique=True, name="uq_staff_member_scope_id",
    )
    await db.staff_members.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("staff_code", ASCENDING)],
        unique=True, name="uq_staff_member_facility_code",
    )
    await db.staff_credentials.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("credential_id", ASCENDING)],
        unique=True, name="uq_staff_credential_scope_id",
    )
    await db.staff_credentials.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("staff_id", ASCENDING), ("registration_authority", ASCENDING), ("registration_number", ASCENDING)],
        unique=True, name="uq_staff_credential_registration",
    )
    await db.staff_credentials.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING), ("submitted_at", ASCENDING)],
        name="ix_staff_credential_review_queue",
    )

    await db.staff_shifts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("shift_id", ASCENDING)],
        unique=True, name="uq_staff_shift_scope_id",
    )
    await db.staff_shifts.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("staff_id", ASCENDING), ("status", ASCENDING), ("starts_at", ASCENDING)],
        name="ix_staff_shift_staff_status_start",
    )

    await db.insurance_claim_appeals.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("appeal_id", ASCENDING)],
        unique=True, name="uq_claim_appeal_scope_id",
    )
    await db.insurance_claim_appeals.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("claim_id", ASCENDING), ("status", ASCENDING)],
        name="ix_claim_appeal_claim_status",
    )
    await db.insurance_claim_appeals.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("claim_id", ASCENDING)],
        unique=True, partialFilterExpression={"status": "submitted"},
        name="uq_one_pending_appeal_per_claim",
    )

    await db.facility_assets.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("asset_id", ASCENDING)],
        unique=True, name="uq_facility_asset_scope_id",
    )
    await db.facility_assets.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("asset_code", ASCENDING)],
        unique=True, name="uq_facility_asset_code",
    )
    await db.facility_assets.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING), ("risk_class", ASCENDING)],
        name="ix_facility_asset_status_risk",
    )
    await db.facility_work_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("work_order_id", ASCENDING)],
        unique=True, name="uq_facility_work_order_scope_id",
    )
    await db.facility_work_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING), ("priority", ASCENDING), ("created_at", ASCENDING)],
        name="ix_facility_work_order_queue",
    )
    await db.facility_work_orders.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("asset_id", ASCENDING), ("created_at", DESCENDING)],
        name="ix_facility_work_order_asset_time",
    )

    await db.safety_incidents.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("incident_id", ASCENDING)],
        unique=True, name="uq_safety_incident_scope_id",
    )
    await db.safety_incidents.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING), ("severity", ASCENDING), ("reported_at", DESCENDING)],
        name="ix_safety_incident_queue",
    )
    await db.safety_investigation_notes.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("note_id", ASCENDING)],
        unique=True, name="uq_safety_investigation_note_id",
    )
    await db.safety_investigation_notes.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("incident_id", ASCENDING), ("recorded_at", ASCENDING)],
        name="ix_safety_investigation_timeline",
    )

    await db.patient_identity_reviews.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("review_id", ASCENDING)],
        unique=True, name="uq_patient_identity_review_scope_id",
    )
    await db.patient_identity_reviews.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("patient_id", ASCENDING), ("reviewed_at", DESCENDING)],
        name="ix_patient_identity_review_patient_time",
    )
    await db.patients.create_index(
        [("tenant_id", ASCENDING), ("facility_id", ASCENDING), ("phone_number", ASCENDING), ("date_of_birth", ASCENDING)],
        name="ix_patient_match_phone_dob",
    )
