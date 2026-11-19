# ODEI Clinic OS — Complete Ecosystem Coverage Register

This register consolidates the scope stated in the supplied Global Blueprint, Global Implementation Master Plan and Master PRD/Technical Specification. It is a coverage register, not a claim that every listed capability is implemented.

## Platform-wide product profile

- Global-first, country-configurable platform.
- Independent clinics, polyclinics, hospitals, mixed facility groups, multi-facility organizations, healthcare networks and national/regional deployments.
- Multi-tenant SaaS, dedicated organization, national/regional, self-hosted and hybrid deployment models.
- Online-authoritative operation, essential offline workflows and extended offline synchronization.
- One longitudinal patient identity and coordinated care journey, with distinct clinical, inventory, financial and operational ledgers.
- Modular monolith first, with durable workers and later service separation only where justified.
- MongoDB operational database, versioned APIs, private object storage, event/outbox processing, reporting projections and provider-neutral deployment.

## Ten mandatory first-release modules

1. Reception: arrival, appointments, check-in, queue management, routing, payments handoff, referrals and human escalation.
2. Registration and medical records: patient search, duplicate review, identity verification, demographics, identifiers, consent/legal-basis records, longitudinal history, documents, corrections/addenda, retention and archival.
3. Outpatient department (OPD): triage, observations, consultations, diagnoses, care plans, clinical orders, prescriptions, referrals and follow-up.
4. Inpatient department (IPD): admissions, ward/bed allocation, transfers, nursing, treatment, medication administration, discharge and reconciliation.
5. Pharmacy and dispensing: authorized prescription validation, safety checks, patient medication history, batch/expiry traceability, partial supply, counselling, returns and wastage.
6. Drug purchasing, procurement and inventory: suppliers, requisitions, approvals, purchase orders, goods receipt/inspection, invoice matching, stock ledger, quarantine, reorder and wastage.
7. Immunization: approved vaccine catalogue/schedules, eligibility, administration, batch/lot tracking, cold chain, temperature excursions, wastage and follow-up.
8. Cash flow, billing and accounting: tariffs, invoices, receipts, payments, allocations, refunds, cash sessions, reconciliation, credit notes and balanced journals.
9. Laboratory and diagnostics: orders, specimen accession and chain of custody, result entry, verification, release, quality control and critical-result escalation/acknowledgement.
10. Insurance and claims: payer configuration, eligibility, preauthorization, claims, rejection/denial management, resubmission and remittances.

## Additional facility and enterprise capabilities

- Emergency services and triage.
- Nursing and procedures.
- Appointments, referrals and continuity-of-care documents.
- Medical records, document scanning, templates, problem lists, patient alerts, medical certificates, referral letters, discharge summaries and consent documents.
- Human resources and payroll.
- Facility administration, equipment, maintenance and asset management.
- Quality assurance, safety and incident reporting.
- Public health and HMIS reporting.
- Patient portal and telehealth.
- Analytics, governed AI assistance and reporting.
- Security, privacy, consent, audit and access review.
- Multi-facility administration, shared identity, facility-level policy and network operations.

Enable clinical/service capabilities only where the facility is licensed, staffed and approved. No AI function may autonomously diagnose, prescribe, triage emergencies or approve clinical/financial actions.

## Shared platform services

- Organization, legal-entity, tenant, facility and department hierarchy.
- Identity, staff credentials, shared patient identity and contextual authorization.
- RBAC plus ABAC; least privilege, separation of duties, emergency access and access review.
- Consent, privacy, legal basis, retention, legal holds and data governance.
- Append-only audit, provenance, immutable history and correction/addendum workflows.
- Workflow orchestration, versioned event contracts, transactional outbox, idempotency, retries and dead-letter/reconciliation handling.
- Terminology, catalogues, country profiles and clinical content governance.
- Notifications, document management and encrypted object storage.
- FHIR and partner/national interoperability adapters.
- Online/offline capture, synchronization, conflict review and reconciliation.
- Analytics projections, operational dashboards and controlled AI assistance.
- Monitoring, security alerts, backup, disaster recovery, downtime and incident response.

## Country-profile dimensions

Each versioned and approved country profile may govern legal/privacy requirements, retention, consent/notice, data residency, clinical governance, scope of practice, terminology, national identifiers, approved formulary, vaccine schedule, laboratory catalogue/ranges, escalation protocols, finance/currency/tax/tariffs/accounting, payers/claims, interoperability, timezone, language and notifications. Historic transactions retain the policy version applied when created. A profile requires an owner, version, effective date, validation evidence and approval.

## Interoperability baseline

- HL7 FHIR release and implementation guide are selected and pinned per integration partner; do not assume one FHIR release is universally correct.
- Assess WHO SMART Guidelines and relevant WHO immunization implementation guidance for maturity and local applicability.
- Uganda deployments require validation against current Ministry of Health EMR/HIE guidance and applicable Ugandan legal and professional requirements.
- Partner integrations require actual counterpart testing and conformance evidence.

## Integrity and safety invariants

- Resolve tenant and facility from authenticated trusted context, never arbitrary client-supplied tenant IDs.
- Every API operation is authorized server-side and scoped to tenant/facility/purpose.
- Preserve authorship, time, reason and prior values for clinical corrections; no silent deletion or overwrite.
- Use idempotency keys and unique constraints for consequential operations.
- Financial corrections use reversals/credit notes; stock balances reconcile to movement ledgers.
- Medication, vaccine, specimen, lab, bed, cash and claim workflows enforce explicit state transitions and traceability.
- Critical online-authoritative operations require server confirmation unless an approved downtime protocol governs them.
- Offline conflicts must be surfaced for authorized reconciliation; never silently overwrite critical clinical, financial or stock records.
- Audit evidence is protected from unauthorized alteration.
- Secrets are write-only at entry and stored in an approved secret manager; application records hold references and metadata only.

## Production release gates

All ten first-release modules must pass acceptance tests; clinical users validate workflows; tenant/facility isolation is proven; medication, laboratory, immunization and inpatient safety controls are tested; stock and financial ledgers reconcile; payment retries cannot duplicate receipts or journals; audit tamper protection is tested; offline conflict handling is safe; backup restoration and disaster recovery are demonstrated; integrations are tested with actual counterparts; country profile is approved; staff training, downtime and incident response are ready. Availability, performance, RPO, RTO, support response and synchronization targets are set with each deployment organization, not invented as universal guarantees.

## Coverage status

The repository currently contains an architecture baseline, MAC/MAD specification/prototype, an API scaffold and health checks. The full ecosystem described above is the target scope. Modules not yet backed by persistent, authorized, tested workflows remain **planned / not implemented**.
