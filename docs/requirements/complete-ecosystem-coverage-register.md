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
| Reception and queue | Partial | Facility-scoped appointment booking, check-in, queue transitions and transactional audit; live queue dashboard, walk-ins, triage priority and wait-time management |
| Patient registration | Partial | Registration, exact MRN or phone+date-of-birth candidate search, human identity-match review; MPI merge, consent, identity verification, guardianship and offline |
| OPD | Partial | Encounter, triage capture with human review/disposition, observations, diagnoses, notes and care-plan foundation; validated clinical pathways, orders, referrals, follow-up and decision support |
| IPD / ADT | Partial | Beds, admissions, transfers, discharge; nursing charts, rounds, escalation and reconciliation |
| Pharmacy | Partial | Medication orders, FEFO dispensing, stock movements and MAR capture for administered/withheld/refused doses; allergies, interactions, formulary, dose scheduling/safety, partial supply, controlled drugs, returns/recalls |
| Procurement / inventory | Partial | Supplier register, draft/submit/segregated purchase-order approval, goods receipts, lots and stock movement events; due diligence, quotations, stock counts, adjustments, valuation, returns and recalls |
| Immunization | Partial | Administration and adverse-event report; schedule, eligibility, consent, cold-chain, follow-up, causality and national reporting |
| Billing / cash | Partial | Invoices, payments, linked cash sessions, chart of accounts and balanced journal posting; automatic subledger posting, refunds, credit notes, tariffs, tax, reconciliation, period close and reporting |
| Laboratory | Partial | Orders, specimen collection and preliminary results; accession, multiple containers, QC, verified release, critical-result escalation and LIS |
| Insurance | Partial | Payers, eligibility evidence, claim submission, manual payer decision and appeal submission; preauthorization, payer integration, remittance, denial/resubmission and settlement |
| Emergency | Partial | Emergency encounter and triage/review foundations; ED episode registration, append-only critical-event/resuscitation documentation, receiving-service handover and clinician disposition decision; actual transfer/admission execution, transport acceptance, protocol support and escalation remain outstanding |
| Nursing / procedures | Partial | Nursing notes, inpatient transfer, assigned nursing tasks with outcomes, SBAR handover and independent acknowledgement; validated assessment scales, fluid balance, wound care, shift rosters, task escalation, procedure checklists and clinical observation escalation remain outstanding |
| Appointments / referrals | Partial | Booking, check-in, queue transitions and initial referral creation/acceptance/closure lifecycle; room/resource capacity, cross-organization acknowledgement, waitlists, referral SLAs and reminders remain outstanding |
| HR / payroll | Partial | Facility staff registry, professional credential submission and independent verification, staff deactivation, future shift scheduling/cancellation; attendance, leave, payroll and approvals |
| Facility / equipment | Partial | Facility asset register, risk classification, maintenance work orders, technician assignment, documented completion and independent release; preventive schedules, calibration due-date enforcement, downtime and serviceability dashboards |
| QA / safety | Partial | Incident and near-miss reporting, investigation notes, root-cause and corrective-action summaries, residual-risk closure; complaints, statutory reporting, CAPA effectiveness and audit programs |
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


- Clinical documentation now supports append-only, separately signed amendments to signed notes, with reason, version counter, transactional audit event and unique amendment-version index. Legal retention, co-signature and late-entry policy remains to be approved.
- Procurement now has a supplier register and segregated purchase-order lifecycle: draft, submit, independent approval and goods receipt only after approval. Competitive procurement, supplier due diligence and spend-limit controls remain outstanding.
- Reception appointment creation now uses the shared appointment document fields and lifecycle, and the cash-session payment flow now serializes payment writes against session closure. These are code-level safeguards; concurrency integration tests and successful CI verification are still pending.


- Triage assessments now enter an awaiting-review state and require an authorized nurse/clinician/facility administrator to record disposition and rationale. Acuity overrides require a reason; encounter priority is updated transactionally only while the encounter remains open. No universal acuity scale or automatic triage score is assumed.
- Observation capture now rejects naive/future effective timestamps. Clinical reference ranges, validated early-warning scores and age-/context-specific escalation remain unimplemented pending approved protocols.

- Workforce governance now includes a facility-scoped staff register, professional credential submission, independent verification/rejection with rationale, expiry checks and audited staff deactivation. It does not yet manage rosters, attendance, leave or payroll; clinical privileges remain separate from HR status.

- Workforce now includes a first roster workflow: future timezone-aware shifts, overlap checks, serialized per-staff roster writes, cancellation with reason and audit. It does not yet implement leave, swaps, attendance, staffing ratios or payroll.

- Insurance now supports appeal submission for rejected/partially accepted claims, prevents simultaneous pending appeals per claim, rechecks payer activity at submission and rejects future-dated eligibility checks. External insurer transmission and remittance remain outstanding.

- Facility operations now includes a scoped asset register and segregated maintenance workflow. Equipment with a recorded service impact remains out of service until a different authorized reviewer releases it with checklist evidence. Preventive maintenance, calibration schedules and facilities inspections remain outstanding.

- Quality and safety now includes append-only incident reporting and investigation notes, role-separated investigation/closure, reporter conflict checks, corrective-action evidence references and audit events. Statutory reporting, CAPA effectiveness and complaints management remain outstanding.

- Patient identity matching now supports facility-scoped candidate search by exact MRN or phone plus date of birth, with an audited human review outcome. It deliberately does not auto-merge records; MPI governance, cross-facility linking, identity proofing and consent remain outstanding.


- Patient privacy now has an initial facility-scoped consent-event register: append-only grant/decline/withdrawal events, purpose and data-category scope, lawful-basis classification, notice version, timezone-aware timestamps, evidence references, audited history reads and scoped indexes. This is not yet a full consent, privacy-rights, retention, guardianship or purpose-based access enforcement system; country-specific legal review remains mandatory.

- Privacy now also includes initial data-subject request case tracking for access, correction, portability, restriction, erasure and objection. Requester identity verification is recorded by privacy officers, status transitions are constrained, and event/audit histories are appended. This does not itself fulfil requests or determine legal exemptions/deadlines.

- Offline synchronization now has an initial secure server intake: facility-scoped Ed25519 device enrollment bound to the enrolling OIDC subject, signed batch verification over canonical payloads, unique batch/change IDs for replay-safe idempotency, bounded payloads, a staged review inbox and audited manual-reconciliation decisions. Incoming payloads are never automatically applied. The encrypted offline client, key lifecycle, conflict engine, per-resource application handlers and approved downtime procedures remain outstanding.


## Additional implementation update — 2026-11-20

- Nursing workflows now include patient/encounter-linked task creation, priority and due time, optional staff-subject assignment, guarded task outcome recording, SBAR handover documentation, structured risk flags and independent acknowledgement. These are task and handover foundations; scheduling/escalation, validated nursing assessment tools, fluid balance, wound care and bedside workflows remain outstanding.
- Emergency department workflows now include one episode per emergency encounter, arrival context, append-only critical-event/resuscitation documentation, receiving-service handover and clinician disposition decisions. Outstanding handovers block disposition. The API records transfer/referral destinations but does not execute external transfers, arrange transport, create inpatient admissions or certify deaths.
- Both modules include scoped authorization, audit events, MongoDB indexes and schema tests. CI for the newest emergency changes was still running at the time of this update; do not treat the additions as production approved.


- Referral management now includes patient/encounter-linked referral creation, urgency and specialty capture, receiving-side acceptance/decline with independent actor and rationale, and outcome-based closure. External receipt and partner interoperability remain unimplemented.
