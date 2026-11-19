# ODEI Clinic OS — Architecture Baseline

Status: controlled engineering baseline; requires clinical, legal, security and operational approval before production.

## Product boundary

A configurable healthcare operations platform for clinics, polyclinics, hospitals, multi-facility organizations and approved regional/national deployments. One governed patient identity and longitudinal record supports coordinated care; clinical, inventory, financial and operational ledgers retain independent controls and provenance.

## Ten first-release domains

1. Reception: arrival, appointments, queues, routing and human clinical escalation.
2. Registration: identity, demographics, identifiers, consent/legal-basis records, duplicate review and longitudinal linkage.
3. OPD: consultations, observations, diagnoses, care plans, orders, prescriptions, referrals and follow-up.
4. IPD: admissions, ward/bed allocation, transfers, nursing, medication administration, discharge and reconciliation.
5. Pharmacy: authorized prescriptions, safety checks, batch/expiry traceability, partial supply, counselling, returns and wastage.
6. Procurement: suppliers, requisitions, approvals, purchase orders, receipt/inspection, invoice matching and quarantine.
7. Immunization: approved catalogue/schedules, eligibility controls, administration, lot tracking, cold chain, wastage and follow-up.
8. Cash flow/accounting: tariffs, invoices, receipts, payments, refunds, cash sessions, reconciliation and balanced journals.
9. Laboratory/diagnostics: orders, specimen accession/chain of custody, result entry, verification, release and critical-result escalation.
10. Insurance/claims: payer configuration, eligibility, preauthorization, claims, rejection management and remittances.

Shared capabilities: organization/facility hierarchy, identity, access policy, workflow orchestration, terminology, consent/privacy, audit, documents, notifications, interoperability, reporting, offline synchronization and governed AI assistance.

Additional configurable capabilities include emergency, maternity, nursing/procedures, referrals, HR/payroll, equipment/maintenance, quality/incident reporting, public-health/HMIS, patient portal and telehealth. Enable only where the facility is licensed, staffed and approved.

## Architecture decisions

- MongoDB is the primary operational database.
- Begin with a modular monolith and durable background workers; split services only when isolation, scale or organizational needs justify it.
- Web: Next.js, React, TypeScript, Tailwind CSS; responsive PWA first.
- API: FastAPI/Python, typed models and OpenAPI 3.1.
- Authentication: secure identity service/OIDC integration, MFA for privileged accounts and strong session controls.
- Authorization: RBAC plus contextual ABAC, enforced server-side for every action and object.
- Events: transactional outbox, versioned contracts, idempotent consumers, retries, backoff and dead-letter/reconciliation handling.
- Real-time: WebSockets or server-sent events.
- Documents: encrypted object storage with private metadata in MongoDB.
- Analytics: separate reporting projections.
- Deployment: Docker, CI/CD, monitored backups and environment-specific configuration.

## Tenancy and country profiles

Support multi-tenant SaaS, dedicated organization, national/regional and self-hosted/hybrid deployments. Resolve tenant context from authenticated identity and trusted session/routing context, never arbitrary client-supplied fields.

Each facility resolves to a versioned, approved country profile covering legal/privacy, clinical governance, terminology, identity, finance, payers, interoperability, timezone, language, notifications and downtime. Activation requires owner, version, effective date, validation evidence and approval. Historic transactions retain the policy version used at creation.

## Data model and integrity

Conceptual collections:
- tenancy: tenants, legal_entities, facilities, departments;
- identity/access: users, role_assignments, staff_credentials, patients, patient_identifiers, consents;
- access/care: appointments, queue_entries, reception_events, encounters, observations, conditions, allergies, clinical_orders, referrals;
- pharmacy/procurement: medication_products, prescriptions, inventory_lots, stock_movements, suppliers, purchase_orders, goods_receipts;
- immunization: vaccine_catalog, vaccine_batches, vaccine_administrations, cold_chain_readings, temperature_excursions;
- diagnostics: lab_orders, specimens, lab_results, result_acknowledgements;
- inpatient: admissions, wards, beds, bed_assignments, nursing_tasks, transfers, discharges;
- finance: invoices, invoice_lines, payments, payment_allocations, refunds, credit_notes, journal_entries, cash_sessions, bank_reconciliations;
- insurance: payers, eligibility_checks, claims, claim_lines, remittances;
- platform: audit_events, outbox_events, sync_operations, country_profile_versions, terminology_versions, workflow_runs, notification_jobs, ai_assistance_events.

Use separate collections for high-volume histories. Apply MongoDB schema validation plus domain state-transition validation. Design compound indexes for tenant/facility scope and profile actual queries. Store UTC timestamps and render in facility timezone. Use fixed precision/integer minor units for money and explicit versioned unit conversions for stock.

Related changes and audit/outbox evidence commit together where MongoDB transactions support them. Critical boundaries include patient+identifier, encounter/order+audit+outbox, goods receipt+lot+stock ledger, dispense+stock movement, bed allocation, and invoice/payment/refund+journal. Use unique indexes and idempotency keys. Financial corrections use reversals/credit notes; stock balances reconcile to append-oriented movement ledgers.

## Domain events

PatientRegistered, AppointmentCheckedIn, EncounterOpened, ClinicalOrderAuthorized, LaboratoryResultValidated, CriticalResultAcknowledged, PrescriptionDispensed, StockReceived, StockQuarantined, VaccineAdministered, TemperatureExcursionDetected, AdmissionAccepted, BedReleased, InvoicePosted, PaymentSettled, ClaimRejected and RefundApproved.

Events carry unique ID, type, schema version, tenant/facility, timestamp, actor/service, aggregate ID/version, correlation ID and minimum necessary payload. Consumers authorize, deduplicate and process idempotently.

## APIs and interoperability

Publish versioned OpenAPI 3.1 contracts. Use RFC 3339 timestamps, timezone handling, stable error codes, correlation IDs, cursor pagination, bounded filters, rate limits and idempotency keys for consequential commands. Never expose stack traces, secrets or unnecessary patient information.

Candidate API domains: patients, appointments, queues, encounters, observations, clinical orders, lab orders/results/release, prescriptions/dispenses, stock receipts, vaccine administrations, admissions, invoices/payments/refunds, claims, reports, audit and device synchronization.

FHIR mappings are partner/profile dependent. Candidate resources include Patient, RelatedPerson, Organization, Location, Practitioner, PractitionerRole, Appointment, Encounter, Observation, Condition, AllergyIntolerance, ServiceRequest, Specimen, DiagnosticReport, MedicationRequest, MedicationDispense, MedicationAdministration, Immunization, Coverage, Claim, ClaimResponse, Invoice, Consent, AuditEvent and Provenance. Pin the release and implementation guide per integration. Use tested R4 profiles where partner requirements call for R4; use R5 only where partner maturity and profiles justify it. Maintain a mapping register with source/target, terminology, transformations, lossiness, version and tests.

Other adapters may include HL7 v2, laboratory instruments, DHIS2/HMIS, national exchange, insurers, payment providers and SMS/email. File exchange requires schema validation, encryption, preview and reconciliation.

## Online/offline policy

Class A safe local capture: registration drafts, permitted queue actions and observation/note drafts in encrypted queues with visible pending status and server validation on sync.

Class B conditional transaction: prescription preparation, result draft, immunization draft and stock count only under explicit facility policy, cached prerequisites and reconciliation.

Class C online-authoritative: high-risk clinical signing, final critical result release, high-value refund, claim finalization and privileged access changes require server confirmation unless an approved downtime protocol governs the action.

Each offline operation includes unique operation ID, actor, device, tenant/facility, base version, local/server timestamps, dependencies and status. Server re-authorizes on reconnect. Responses distinguish accepted, rejected, needs-review and conflict. Never use last-write-wins for clinical, medication, vaccine, inventory, financial or bed conflicts. Preserve original values and reconciliation decisions.

Facilities need downtime packs and drills for identification, encounter numbering, prescriptions, specimens, vaccine records, receipts, emergency escalation and reconciliation after restoration.

## Clinical safety and AI

Maintain a hazard log with safety owner, severity/likelihood, mitigations, tests and residual risk. Clinical rules require named clinical owner, authoritative source, version, effective date, validation set and rollback. Preserve units, reference ranges and provenance. Critical-result workflows track delivery, acknowledgement, escalation and closure.

AI may assist with summaries, workflow preparation, missing follow-up detection, forecasting and draft documentation. Clearly distinguish AI output from verified clinician-authored content. Record model/ruleset version, input references, output, user, time and acceptance/rejection. AI does not autonomously diagnose, prescribe, administer medication, determine emergency triage or override approved protocols. Humans retain clinical and financial approval authority.

## Security, privacy and audit

TLS in transit; encryption at rest and for backups; secrets outside source code/images; MFA for privileged users; step-up auth for high-risk actions; session/device revocation; least-privilege database/service accounts; restricted networks/admin interfaces; OWASP-aligned threat modelling; secure uploads and malware scanning; dependency scanning, patching and penetration testing.

Map purposes, legal bases, recipients and retention per country. Consent is not presumed to be the legal basis for every healthcare process. Audit actor, action, target, tenant/facility, time, purpose, outcome, source device and correlation ID. Audit sensitive reads where required; never log credentials/tokens or excessive clinical payloads. Protect append-oriented audit storage separately and monitor tampering.

## Release gates

No live patient care until all ten domains pass acceptance tests; clinicians validate workflows; tenant/facility isolation negative tests pass; medication/lab/immunization/IPD safety controls pass; stock and financial ledgers reconcile; retries cannot duplicate postings; audit integrity is tested; offline conflicts reconcile safely; restore/disaster recovery is demonstrated; actual integrations are tested; country profile is approved; and training, downtime and incident response are ready.

Availability, latency, RPO, RTO, support and synchronization targets are deployment-specific. The PRD's proposed pilot RPO ≤15 minutes and RTO ≤4 hours are targets subject to business-impact analysis and infrastructure capability, not guarantees.
