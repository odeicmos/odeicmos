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


## Repository implementation status — 2026-11-19

This is a conservative status snapshot of committed code, not a production-readiness assertion.

| Capability | Current code status | Important remaining work |
|---|---|---|
| Reception and queue | Partial | Appointment booking/check-in/cancellation; live arrival queue, routing and wait-time management |
| Patient registration | Partial | MPI matching/merge, consent, identity verification, guardianship, duplicate review, offline |
| OPD | Partial | Triage/observations/diagnoses/notes/care-plan foundation; full order, referral, follow-up and clinical decision support |
| IPD / ADT | Partial | Beds, admissions, transfers, discharge; nursing charts, rounds, escalation and reconciliation |
| Pharmacy | Partial | Medication orders, FEFO dispensing, stock movements and MAR capture for administered/withheld/refused doses; allergies, interactions, formulary, dose scheduling/safety, partial supply, controlled drugs, returns/recalls |
| Procurement / inventory | Partial | Purchase orders, goods receipts, lots and stock movement events; supplier governance, approvals, stock counts, adjustments, valuation, returns and recalls |
| Immunization | Partial | Administration and adverse-event report; schedule, eligibility, consent, cold-chain, follow-up, causality and national reporting |
| Billing / cash | Partial | Invoices, payments, linked cash sessions, chart of accounts and balanced journal posting; automatic subledger posting, refunds, credit notes, tariffs, tax, reconciliation, period close and reporting |
| Laboratory | Partial | Orders, specimen collection and preliminary results; accession, multiple containers, QC, verified release, critical-result escalation and LIS |
| Insurance | Partial | Payers, recorded eligibility, claim submission and manual decision; preauthorization, payer integration, remittance, denial/resubmission and settlement |
| Emergency | Partial | Encounter type and triage primitives only; emergency protocols, resuscitation, observation/escalation and transfer |
| Nursing / procedures | Partial | Nursing note and inpatient transfer primitives; task lists, MAR, procedures, checklists and clinical observation escalation |
| Appointments / referrals | Partial | Booking, check-in and cancellation; room/resource capacity, waitlists, referrals and reminders |
| HR / payroll | Not implemented | Staff registry, credentials, rota, attendance, payroll and approvals |
| Facility / equipment | Not implemented | Departments, assets, maintenance, calibration, downtime and serviceability |
| QA / safety | Not implemented | Incidents, complaints, audit programs, corrective actions and clinical governance |
| Public health / HMIS | Not implemented | Aggregations, validated reporting, DHIS2/national adapters and submission reconciliation |
| Patient portal / telehealth | Not implemented | Identity proofing, proxy access, messaging, remote visits and patient-facing records |
| FHIR / interoperability | Not implemented | Version-pinned FHIR resources, profiles, terminology, conformance and partner testing |
| Offline operation | Not implemented | Durable local store, encryption, signed sync, idempotency, conflict review and downtime protocol |
| MAC / MAD | Partial | Prototype/specification and control-plane APIs; production operations, approvals, observability and safe provider adapters |
| Security / privacy | Partial | OIDC, scoped roles and audit events; ABAC/purpose controls, consent, retention, key lifecycle, immutable audit enforcement, penetration testing |
| AI governance | Not implemented | No autonomous clinical decisions; governance, evaluation, provenance, human review and audit controls required |

No capability marked partial is approved for live patient care, medication use, financial close or regulatory reporting solely because an endpoint exists. Every production deployment still requires end-to-end workflow tests, facility validation, security review, clinical sign-off, data migration/restore drills, operational training and country-specific approval.


## Additional implementation update — 2026-11-19

- Accounting now includes facility-scoped chart-of-accounts setup and balanced, idempotent double-entry journal posting with transactionally appended audit events. This is not a complete general ledger and database-level immutability still needs enforcement.
- Pharmacy now includes an initial medication administration record endpoint for administered, withheld and refused doses against a dispensed order. It checks that the prescribed line is unambiguous and prevents cumulative recorded administration from exceeding dispensed quantity. It does not perform clinical dose validation, allergy/interaction checks or bedside identity/barcode verification.
- New schema tests cover journal balance/line invariants and medication-administration decision fields. These tests are committed but have not been confirmed by a successful CI run.


- Reception now has facility-scoped appointment creation, appointment check-in and waiting/in-service/completed/cancelled queue transitions. Provider/room scheduling conflicts and full queue routing are not yet implemented.
