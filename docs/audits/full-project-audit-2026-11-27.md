# ODEI Clinic OS — Full Repository Audit

**Audit date:** 2026-11-27  
**Repository:** https://github.com/odeicmos/odeicmos  
**Branch reviewed:** `main`  
**Reviewed tree:** `b3cc168503ebf06979856fdea32fe87373fd9d95`  
**Audit type:** Static repository, architecture, API surface, security-control, test, documentation and release-readiness audit.  
**Limitations:** This review does not constitute a penetration test, independent clinical safety assessment, legal opinion, live database test, load test, disaster-recovery exercise, or verification of external provider accounts. No production infrastructure or patient data was accessed.

## 1. Executive verdict

**Overall status: NOT PRODUCTION READY — DO NOT USE FOR LIVE PATIENT CARE OR LIVE FINANCIAL PROCESSING.**

The repository contains a meaningful FastAPI/MongoDB foundation and a growing set of domain workflow slices. It is materially beyond an empty scaffold. However, it is not yet the complete ODEI Clinic OS described by its architecture and coverage register.

The current code has 22 API routers registered in `main.py`, a single large index-provisioning function, a standalone HTML control-plane prototype, API tests, architecture/requirements/security documentation, and a draft Uganda country profile. Most domain capabilities are partial workflow foundations rather than complete operational modules.

A successful CI run establishes only that the configured focused lint and automated test commands passed for that commit. It does not establish clinical safety, production security, full business correctness, data integrity under concurrency, operational readiness, regulatory compliance or interoperability.

### Release decision

| Area | Audit result | Release consequence |
|---|---|---|
| Architecture and repository structure | Partial foundation | Continue engineering |
| API and domain workflows | Partial; many write-only workflow slices | Not operationally complete |
| Authentication | OIDC RS256 foundation | Hardening and lifecycle controls required |
| Authorization / tenancy | Facility-role checks exist | Not yet sufficient for production ABAC and lifecycle governance |
| Audit and accountability | Transactional audit writes exist | Immutability and comprehensive access logging unproven |
| Database integrity | Many indexes and transactions | Migration lifecycle, integration and concurrency validation incomplete |
| Clinical safety | Several guarded workflows | Critical clinical pathways and independent validation missing |
| Finance and inventory integrity | Initial ledgers and movements | Reconciliation, reversal, close and subledger controls incomplete |
| Offline | Signed intake and manual review | No working offline client or conflict application engine |
| MAC / MAD | Specification and static prototype | No production control-plane operations or observability platform |
| Frontend | Standalone prototype only | No production application frontend |
| Deployment / operations | Limited runbook and env examples | No verified deploy, backup, restore, DR or monitoring evidence |
| Uganda compliance | Draft checklist | No approval to process live personal data |
| Tests / CI | Focused CI passes for latest reviewed commits | Insufficient test depth for release |

## 2. Repository inventory and implementation footprint

The reviewed tree contains:
- FastAPI application and 22 registered routers.
- MongoDB configuration, connection lifecycle, explicit migration CLI and one consolidated index function.
- OIDC JWT/JWKS verification and facility-role authorization primitives.
- Transactional audit event writer.
- Domain APIs for control plane, patients, clinical records, inpatient, appointments, reception, pharmacy, laboratory, immunization, finance, accounting, procurement, insurance, workforce, facility operations, safety, privacy, offline sync, nursing, emergency, referrals and procedures.
- Schema-focused tests for many domains plus health and limited authorization tests.
- One standalone `apps/control-plane-mvp/index.html` prototype.
- Architecture, API, security, operational, requirements and country-profile documents.

The current API router registration is materially broader than the README's older scaffold description. The README contains contradictory historical claims that authentication, persistence and business endpoints do not exist. Those statements must be corrected so operators and reviewers are not misled.

The root repository does not contain a production frontend application manifest/build, Dockerfile/container build, Kubernetes or equivalent deployment manifests, infrastructure-as-code, a production worker service, or a release pipeline for the complete platform. The single API workflow is scoped to `apps/api/**` and its workflow file.

## 3. Critical and high-priority findings

### C-01 — Production release is not authorized

**Severity: CRITICAL — release blocker**

The README itself states that the platform is not certified or approved for live clinical use. The Uganda country profile is explicitly draft and not approved. No evidence was found in this repository of clinical governance approval, independent security assessment, facility acceptance, regulator approval, data-protection registration evidence, live partner conformance or production disaster-recovery testing.

**Required:** Keep production patient-data processing disabled until the formal release gates in section 11 are evidenced and signed by accountable owners.

### C-02 — Authentication key cache has no bounded lifetime

**Severity: HIGH**

`security.py` caches the OIDC JWKS document in a process-global verifier object and does not attach a TTL, refresh schedule, stale-key policy or bounded cache lifetime. It refreshes on an unknown `kid`, but a still-present key can remain cached indefinitely after issuer-side key rotation or revocation.

**Required:** Implement bounded TTL and safe refresh, issuer metadata validation, cache stampede protection, key-rotation tests, timeout/availability policy and security-event telemetry. Test issuer outages and compromised-key removal.

### C-03 — Role assignment lifecycle is incomplete

**Severity: HIGH**

`authorize_facility_access` checks tenant, facility, issuer, subject, active status and allowed role. The visible authorization query does not check assignment start/end times, expiry, suspension metadata, credential/privilege status, or an access-review state. Control-plane code exposes role-assignment creation but no complete role revocation, expiry, delegated administration or periodic access-review workflow was found.

**Required:** Add effective-from/effective-until, revocation, suspension, approver, reason, role catalog governance, privileged MFA/step-up, access review and emergency-access procedures. Ensure staff deactivation and professional credential expiry invalidate applicable clinical privileges, rather than treating HR status and clinical privilege as disconnected facts.

### C-04 — Audit immutability is documented, not enforced by code

**Severity: HIGH**

`audit.py` appends events and comments that the MongoDB audit writer role must be configured with insert/find only and update/delete denied. The repository does not provision or verify that role, demonstrate a denial test, protect audit records against privileged database operators, or provide tamper-evident chaining/external immutable export. Audit event structure does not consistently include purpose of use, facility as a first-class field, request context, before/after state, source channel or full correlation context. Many read operations across the system are not represented by explicit read-audit events.

**Required:** Provision separate least-privilege DB roles through infrastructure automation; prove update/delete denial in integration tests; add tamper-evident retention/export; define complete audit event schema and read-access policy; audit sensitive reads and all privileged control-plane changes; test failure behavior when audit storage is unavailable.

### C-05 — Readiness is not a production dependency check

**Severity: HIGH**

`main.py` readiness checks that MongoDB ping succeeded and OIDC issuer/audience/JWKS URL strings are configured. It does not verify a successful JWKS fetch/token-verification path, migration/index version, secret-manager availability, object storage, worker/outbox health, queues, telemetry, encryption/key services or actual downstream integration health. The MongoDB connection exception is swallowed without structured logging. Readiness can therefore report ready while critical runtime dependencies are broken or the database is not migrated.

**Required:** Add explicit dependency probes with safe timeouts and clear degraded states; verify required migration version; distinguish liveness/readiness; emit structured startup and dependency failure telemetry; never expose secrets or internal details in health responses.

### C-06 — Database migration lifecycle is not a true versioned migration system

**Severity: HIGH**

`migrate.py` calls one large `apply_control_plane_indexes` function. The function now creates indexes for many domains, but there is no migration ledger, ordered migration registry, applied-version history, checksum, preflight/rollback strategy or automated deployment gate. A single failure can leave a partially provisioned schema without an explicit migration state. MongoDB transactions require a replica set or sharded deployment; no production database topology has been verified.

**Required:** Create numbered, immutable migrations with a migration history collection, preflight checks, idempotency, failure/retry policy, lock/concurrency control, index drift checks and tested upgrade/restore paths. Verify transaction support on the actual target topology.

### C-07 — API tests do not establish end-to-end correctness

**Severity: HIGH**

The repository's domain tests are predominantly schema/model tests. The limited health tests and facility-authorization fake test do not substitute for real API/database integration tests. No comprehensive evidence was found for real MongoDB transactions, rollback, concurrent requests, cross-tenant denial, cross-facility denial, role revocation, object-level access, audit failure, idempotent retry, duplicate race, or full clinical/financial workflow tests.

**Required:** Add disposable replica-set integration testing; route-level tests with real authentication fixtures; negative authorization matrix; concurrency and fault-injection tests; migration tests; end-to-end scenarios; contract tests and load/security testing. Keep focused lint, but add formatting/type/security/dependency and secret scanning rather than treating the current narrow Ruff selection as comprehensive quality assurance.

### C-08 — No production data-plane frontend or deployable platform is present

**Severity: HIGH**

`apps/control-plane-mvp/index.html` is a standalone prototype, not a production application. The repository has no production Next.js/React/TypeScript application package, authenticated UI, facility workflows, patient-facing interface, API-generated client, deployment build, or production frontend tests. The prototype's synthetic values must not be represented as live system telemetry.

**Required:** Build the production web/PWA and role-aware workflows; connect only to authenticated APIs; remove mock status from operational claims; add accessibility, responsive, offline, session security and frontend test gates.

## 4. Platform security, privacy and tenancy audit

| Control | Finding | Required completion |
|---|---|---|
| OIDC | RS256/JWKS validation foundation exists | TTL cache, issuer metadata, rotation/revocation tests, MFA/step-up, session controls, logout/revocation and operational monitoring |
| RBAC | Facility assignments checked per route | Role catalog, effective dates, revocation, privilege separation and access reviews |
| ABAC | Not comprehensively implemented | Purpose of use, care relationship, patient sensitivity, consent, break-glass, time/location/context policies |
| Tenant isolation | Many queries explicitly include tenant/facility | Automated exhaustive isolation tests for every route and every related-resource lookup |
| Facility lifecycle | Some endpoints check active facilities; not a uniform dependency | Central active-facility/tenant guard and suspension/closure handling |
| Audit | Transactional append helper | Enforced DB immutability, read auditing, tamper evidence, retention, monitoring and audit export |
| Secrets | Environment-based secret injection pattern | Secret-manager adapter, rotation, least privilege, access logging and production verification |
| Encryption | Not demonstrated by application configuration | TLS enforcement, at-rest/object/backup encryption, key management and rotation evidence |
| Rate/resource limits | No comprehensive middleware evidence | Request/body limits, per-principal/device throttles, abuse controls, query limits and timeouts |
| HTTP security | No production security middleware evidence | Trusted hosts, secure headers, CORS allowlist, TLS termination policy, CSRF strategy where applicable |
| Privacy | Consent events and data-subject request case tracking exist | Purpose enforcement, notice lifecycle, rights fulfilment, deadlines, retention/deletion, legal holds, guardianship and cross-border transfer assessment |
| Sensitive data | Some projections are role-dependent | Field-level minimization for every endpoint, encryption of especially sensitive fields, safe logging and data export controls |
| Object storage | Evidence references are strings in some workflows | Private encrypted object storage, signed URLs, malware scanning, retention and access checks |
| Incident response | Safety incident workflow is a clinical QI feature | Separate cybersecurity incident playbook, breach assessment, notification deadlines, forensic preservation and tabletop exercises |

**Important:** A `confidential` flag or a consent event is not, by itself, an access-control policy. The application must enforce the applicable purpose, scope, legal basis and access decision on each data operation.

## 5. Domain-by-domain functional audit

Status labels: **Partial** means a limited API workflow exists; it does not mean the complete module is operational. **Missing** means no meaningful production implementation was found in the reviewed repository.

| Domain | Current implementation found | Missing / incomplete scope |
|---|---|---|
| Tenant and organization control plane | Tenant, organization, facility and role-assignment creation | Read/list/update/deactivate lifecycle, delegated admin, approval workflow, full policy/configuration registry, entitlements, environment/secret references, deployment orchestration |
| Patient registration and records | Registration, demographic retrieval, exact MRN or phone+DOB candidate search, human identity review | Global MPI, cross-facility identity, verified identity evidence, merge/unmerge governance, guardianship/proxy, patient history aggregation, document store, record correction/retention/archive, comprehensive access control |
| Reception | Appointment creation, check-in, queue transitions | Walk-ins, full desk dashboard, service routing, provider/resource capacity, triage handoff, wait-time/SLA, no-show, notifications, payments handoff |
| OPD / clinical | Encounters, notes, signing/amendments, triage review, observations, diagnoses, care plans | Complete consultation workspace, structured history/exam, allergy/problem/medication reconciliation, orders, result review, clinical pathways, follow-up and discharge workflow |
| IPD / ADT | Bed register, admission, bed transfer, discharge | Ward rounds, nursing charts, vitals schedule, intake/output, medication chart integration, discharge planning, bed cleaning/turnover, census and occupancy board, transfer escalation |
| Nursing | Task creation/outcomes, SBAR handover and acknowledgement | Validated nursing assessments, care plans/tasks execution outcomes, medication/IV charts, wound/pressure injury, fluid balance, falls, observations schedule, rostering escalation, bedside devices |
| Emergency | Emergency episode, critical event, handover/acknowledgement, disposition | Full triage/acuity pathway, resuscitation protocol support, time-critical alerts, ED board, observation/reassessment, admission execution, transport/transfer acceptance, death-certification governance |
| Procedures | Request, checklist, time-out, start and completion record | Privilege verification, specialty-specific checklists, sedation/anaesthesia, recovery, implant/consumable traceability, pathology, legal consent workflow, post-op observations and adverse-event pathways |
| Referrals | Referral creation, receiving decision and closure | Cross-organization identity, secure external transmission/receipt, appointment booking, transport, partner acknowledgement, SLA escalation, national referral directory |
| Pharmacy | Medication order, FEFO dispensing, inventory movement, MAR event | Medication catalogue/formulary, allergy/interactions, dose/route/frequency validation, weight/renal/hepatic dosing, partial supply, counselling, reconciliation, controlled drugs, returns, recalls, barcode verification, medication incident monitoring |
| Procurement | Supplier register, draft/submit/independent PO approval, goods receipt, lot creation | Requisitions, quotations/tenders, thresholds, contracts, due diligence, invoice three-way match, payment, supplier statements, inspection/quarantine, returns/recalls, stock counts and valuation |
| Inventory | Lot tracking and selected stock movement events | Unified append-only stock ledger for all adjustments/transfers/returns/expiry/wastage, reservation, stocktake, valuation, multi-store transfers, reorder, quarantine, recall and reconciliation |
| Laboratory | Orders, one specimen per order, preliminary result entry | Accession/barcode, multiple specimens/containers, rejection/recollection, chain of custody, analyzer/LIS, QC, reference range governance, verified/final/amended results, critical-result acknowledgement |
| Immunization | Administration record, batch expiry check, adverse-event report | Schedule/eligibility/contraindication, consent, interval/catch-up, vaccine stock issue, cold-chain telemetry/excursion, wastage, reminders, AEFI investigation, national reporting |
| Billing / finance | Invoice, payment, overpayment guard, cash sessions and variance, chart of accounts and balanced journal endpoint | Tariffs/price lists, tax/discount, credit notes/refunds/voids, payer allocations, automatic subledger-to-GL posting, bank/mobile-money reconciliation, receivables ageing, period close, audit/reporting and financial statements |
| Insurance | Payers, eligibility evidence, claims, manual decision, appeal submission | Preauthorization, payer-specific mapping, secure submission, acknowledgements, remittance advice, denial coding, resubmission, settlement reconciliation, contracts and coverage rules |
| Workforce | Staff registry, credential submission/decision, staff deactivation, shift creation/cancellation | Payroll, attendance, leave, overtime, swaps, staffing ratios, recruitment, training, appraisals, disciplinary process, credential source verification, privilege matrix and roster-to-authorization linkage |
| Facility / equipment | Asset register, work order, assignment, completion and independent release | Preventive maintenance, calibration schedules and due enforcement, inspections, facilities, utilities, biomedical service contracts, spare parts, asset depreciation, downtime dashboards and technician qualification verification |
| Quality / safety | Incident/near-miss report, investigation notes, role-separated closure | Complaint case management, CAPA workflow/effectiveness, infection surveillance, risk register, audit programme, statutory reports, regulator notification and analytics |
| Privacy | Consent/lawful-basis event log; data-subject request case workflow | Automated purpose enforcement, identity proofing, fulfilment/export/rectification/erasure, deadline/legal exemption, retention schedules, legal holds, guardianship, processor register and breach workflow |
| Offline | Ed25519 device enrollment/revocation, signed batch intake, staged inbox, manual review | Encrypted offline local DB, PWA/mobile client, key rotation, clock drift, sync retry protocol, conflict resolution, resource-specific application, attachment transfer, offline audit and approved downtime operations |
| MAC | Static prototype, control-plane docs and tenant/facility/role creation APIs | Production console, MFA/step-up, approval queues, policy engine, secret manager, provider adapters, release/deployment/rollback, backup controls, access reviews, full lifecycle and immutable admin audit |
| MAD | Product specification only | Actual telemetry, service health, worker/queue/DB metrics, stale-data indicators, incident/alert management, cost/capacity dashboards and aggregate reporting |
| Public health / HMIS | No production workflow found | DHIS2/national reports, indicator definitions, de-identification, submission, acknowledgements and reconciliation |
| FHIR / interoperability | Architecture intent and version-pinning guidance | FHIR resources/profiles, terminology service, mappings, validation, OAuth/SMART where required, partner sandbox tests, conformance and message reconciliation |
| Patient portal | No production implementation found | Patient identity proofing, consent, proxy/guardian, records, appointments, results, payments, messaging and accessibility |
| Telehealth | Encounter type permits telehealth label | Secure video, scheduling, identity, consent, prescribing scope, clinical documentation and integration |
| AI | No governed AI implementation found | Use-case registry, risk classification, data controls, evaluations, provenance, human review, model monitoring, audit, opt-out and safety incident handling |
| Reporting / analytics | No complete reporting service found | Defined metrics, reporting projections, row/field permissions, audit, exports, scheduled reporting and regulator-ready reconciliation |
| Notifications | No durable notification service found | SMS/email/push adapters, templates, delivery receipts, retries, consent/preferences and escalation |
| Documents | Evidence references only in selected schemas | Secure document service, malware scanning, versioning, retention, access policy, signatures and patient association |
| Background processing | No complete worker/outbox implementation found | Transactional outbox, durable queue, retries, dead-letter queue, idempotent consumers, monitoring and replay |
| Multi-region / deployment | Architecture intent only | Region/data-residency routing, tenant isolation profile, HA, DR, self-hosted/hybrid automation and verified deployment profiles |

## 6. Specific code and workflow risks requiring targeted review

These are static-review findings or test gaps that should be treated as engineering tasks and validated with targeted tests before any production use.

1. **JWKS cache:** process-global, no bounded TTL or explicit issuer key revocation policy.
2. **Authorization lifecycle:** no expiry/revocation check in the facility authorization query; no full role-assignment lifecycle surfaced.
3. **Facility active-state enforcement:** active-facility checks are not a shared dependency applied uniformly across every route.
4. **Patient identity review:** review outcomes are recorded, but no merge/unmerge workflow, dual-control review or identity evidence model exists.
5. **Patient read access:** role-specific projections are a useful start, but purpose-of-use and care-relationship rules are not enforced. The clinician/nurse response returns the full stored patient document unless explicitly projected.
6. **Clinical note governance:** signing and amendment foundations exist; co-signature, late-entry policy, correction visibility, version history reads and legal retention rules are not complete.
7. **Clinical terminology:** diagnosis and observation codes are caller-supplied strings; no validated terminology catalogue or unit system enforces code/value compatibility.
8. **Triage:** acuity is an integer with human review; no locally approved scale, required vital set, reassessment timer or escalation policy is enforced. This is not a validated triage product.
9. **Appointments:** overlap detection is a query inside a transaction, but no database-enforced exclusion/serialization guarantee for practitioner/time intervals is evident; concurrent booking tests are needed. Practitioner identity/active status and room/resource capacity also require validation.
10. **Inpatient:** atomic bed movement is a useful foundation; end-to-end admission/discharge/transfer concurrency and cross-resource invariants need real replica-set tests. Bed cleaning/turnover and ward workflows are absent.
11. **Pharmacy:** FEFO allocation is not equivalent to medication safety. No clinical decision support or comprehensive inventory transaction coverage exists. Test partial dispensing, concurrent dispense, lot depletion, expiry boundaries and rollback.
12. **Laboratory:** current workflow permits preliminary result capture only. Multiple analytes/results, final verification, amendments, specimen rejection and critical-result workflows are absent. Concurrency and duplicate result tests are required.
13. **Immunization:** no vaccine schedule/eligibility or cold-chain control. Batch expiry and administration timestamp are only a small subset of safe vaccination controls.
14. **Finance:** balanced journal schema is not a complete general ledger. There is no proven automatic posting/reconciliation from invoices, receipts, inventory, payroll and claims. Test concurrent payments, cash close races, refunds and journal idempotency against a real replica set.
15. **Procurement/inventory:** approval segregation exists, but goods receipt/stock valuation and supplier lifecycle are incomplete. Test concurrent receipt, over-receipt, duplicate receipt and order-line reconciliation.
16. **Insurance:** eligibility and claims are locally recorded; no external payer integration or settlement. Confirm claim amount basis and invoice balance semantics before extending.
17. **Workforce:** HR deactivation and professional credential records are not yet proven to revoke existing role assignments or clinical privileges. Assignment of technicians/nurses to work should validate active staff and relevant qualification.
18. **Facility maintenance:** independent release is a positive control; asset calibration due dates and technician competency are not enforced.
19. **Safety incident confidentiality:** `confidential` is metadata, not an access-control boundary. Incident GET/list, case permissions and sensitive evidence storage are not complete.
20. **Privacy:** consent events are historical records, not an enforcement engine. Data-subject request status tracking does not perform the underlying export, correction, restriction or erasure.
21. **Offline sync:** signed intake and review inbox do not apply changes. Device private-key custody, key rotation, clock drift, replay/flood protection, attachment security and resource-specific conflict resolution are unproven.
22. **Control plane:** only a small registry subset is backed by APIs. The documented provider, deployment, secrets, release, rollback and observability control plane is not implemented.
23. **Error handling:** broad exception handling in selected paths should be narrowed and tested; avoid exposing raw database errors or suppressing operational failures.
24. **Idempotency:** explicit idempotency keys exist in selected financial/medication flows, not consistently across all mutation endpoints and external callback boundaries.
25. **Read surfaces:** many resources have create/action endpoints but no list/detail/history endpoints or pagination contracts, preventing complete operational workbenches.
26. **State machines:** workflow transitions are implemented locally in route handlers; there is no shared formal state-machine/event contract or systematic transition-table test suite.
27. **Data retention:** no automated retention, archive, deletion, legal-hold or backup-expiry implementation was found.
28. **Observability:** no complete structured logging, metrics, tracing, alerting, SLO, audit review or dashboard service was found.
29. **API governance:** version prefix exists, but no published compatibility/deprecation policy, generated SDK, schema-diff gate or comprehensive error envelope was found.
30. **Deployment security:** no production container hardening, SBOM/signing, dependency vulnerability gate, secret scan, image scan, infrastructure policy or rollback workflow is present in the reviewed tree.

## 7. Test and CI audit

### What is present

- GitHub Actions API workflow installs the package, runs focused Ruff checks (`E4,E7,E9,F`) and runs pytest.
- Latest reviewed runs for procedure consent evidence, procedure workflow, referrals, emergency, nursing and signed offline sync changes show successful completion.
- Tests cover many schema constraints and selected authorization/health behavior.

### What is not established

- The workflow is not a complete quality/security pipeline.
- The tests do not prove real MongoDB transactions or production topology behavior.
- No complete route-level authorization matrix exists.
- No systematic tenant/facility isolation suite exists.
- No concurrency, load, chaos, failure-injection or restore tests exist.
- No browser/frontend tests exist.
- No interoperability contract tests exist.
- No clinical simulation or usability acceptance evidence exists.
- No coverage threshold or coverage report is configured.
- Ruff's focused selection does not establish full formatting/style compliance, type correctness, security lint or dependency safety.
- The workflow only triggers for API code/workflow paths; documentation, country profiles and UI changes do not receive their own validation pipeline.

**Required CI expansion:** unit + schema tests, replica-set integration tests, route/authorization tests, migration tests, contract tests, frontend tests, coverage thresholds, type checking, full lint/format, dependency vulnerability scan, secret scan, SAST, container scan, SBOM and release artifact signing.

## 8. Documentation and governance defects

1. README contains contradictory and obsolete status statements.
2. The coverage register is a useful inventory but should become a controlled requirements traceability matrix with stable requirement IDs, owners, evidence, acceptance tests and release status.
3. API documentation is a large manually maintained file; generate and diff against FastAPI OpenAPI to prevent drift.
4. Architecture documents describe target capabilities that do not yet exist; label each target vs implemented capability consistently.
5. Uganda profile is draft; legal/privacy, clinical, finance, security, operations and facility approvals are not evidenced.
6. No formal data dictionary, terminology governance, role catalogue, privilege matrix, threat model with abuse cases, clinical hazard log, DPIA, processing inventory or retention schedule was found as an approved artifact.
7. No versioned release policy, support policy, incident response plan, change management policy, downtime SOP or operational service catalogue was found in complete executable form.
8. No license is declared; ownership, licensing, contribution and release authority still require governance approval.

## 9. Uganda pilot-specific blockers

The Uganda profile must remain draft until qualified local review confirms:
- Current PDPO registration and controller/processor obligations for each entity.
- Lawful basis, patient notices, data-subject rights, retention and breach response.
- Hosting/data location and cross-border transfer requirements.
- Processor/subprocessor contracts, backup location and key ownership.
- Facility licensing and service scope.
- Professional registration and privileges.
- Ministry of Health reporting, HMIS/DHIS2 and any applicable EMR/interoperability requirements.
- Approved local clinical protocols, triage, formularies, vaccine schedules, laboratory reference ranges and critical-result pathways.
- UGX accounting configuration, tax, tariffs, payer contracts and payment-provider reconciliation.
- Language, accessibility, timezone, date format and downtime operations.

No Uganda-specific approval or regulatory status should be inferred from the draft country profile.

## 10. Prioritized remediation programme

### P0 — Stop unsafe production use
1. Keep the environment non-production; do not load live patient records.
2. Rotate the MongoDB credential previously exposed in project conversation; inspect access logs and remove any accidental credential from repository history if applicable. Never put replacement credentials in Git.
3. Establish named owners for security, clinical safety, privacy/legal, finance, operations and release authority.
4. Freeze the release checklist and explicitly mark every unverified integration as disconnected.

### P1 — Security and data integrity foundation
1. Harden OIDC JWKS cache, key rotation and session lifecycle.
2. Implement role assignment expiry/revocation and clinical privilege lifecycle.
3. Add central tenant/facility/purpose authorization dependencies.
4. Enforce immutable audit DB permissions and tamper-evident export.
5. Implement robust readiness/dependency probes and structured logs/metrics.
6. Build versioned migrations and validate replica-set transaction behavior.
7. Add rate limits, request limits, secure headers, CORS, secret manager and object-storage controls.
8. Add route-level and cross-tenant integration tests.

### P2 — Complete core clinical and operational workflows
1. MPI/identity proofing, consent enforcement and longitudinal records.
2. OPD complete consultation, diagnoses, orders, allergies, medications and results.
3. IPD/ADT, nursing observations, fluid balance, medication chart and discharge.
4. Emergency triage/reassessment/escalation and transfer/admission execution.
5. Medication safety, formulary, reconciliation, partial supply, returns and recalls.
6. Laboratory accession, QC, verification, critical result and LIS integration.
7. Vaccine schedules, eligibility, cold chain and AEFI reporting.
8. Inventory ledger, stocktake, valuation, procurement matching and recalls.
9. Complete billing, payments, refunds, reconciliation, GL subledgers and period close.
10. Insurance preauthorization, external claims, remittance and settlement.
11. HR credential-to-privilege linkage, facility maintenance and safety CAPA.

### P3 — Complete the ecosystem platform
1. Production web/PWA, patient portal and role-specific workbenches.
2. Production MAC/MAD with approvals, provider adapters, secret references, deployment/rollback and observability.
3. Offline local encrypted client and resource-specific conflict engine.
4. FHIR/terminology, partner interfaces, DHIS2/HMIS and notification service.
5. Document/object storage, durable outbox/workers, analytics and governed AI.
6. Multi-region, self-hosted/hybrid deployment automation and tenant migration.

### P4 — Verify and authorize release
1. Independent penetration test and remediation.
2. Clinical hazard analysis, simulation, usability testing and clinical sign-off.
3. Facility acceptance and staff competency/training.
4. Data migration rehearsal, backup restore and DR exercise with approved RPO/RTO.
5. Load, failover, offline and concurrency tests.
6. Country/legal/privacy approvals and external partner conformance.
7. Signed release approval and monitored, reversible pilot rollout.

## 11. Mandatory production release gates

A production launch is blocked until all of the following have evidence and accountable sign-off:

- [ ] Security architecture and threat model approved.
- [ ] Independent penetration test completed; critical/high findings closed or formally risk-accepted.
- [ ] Tenant/facility/purpose access tests pass for every resource and endpoint.
- [ ] OIDC key rotation, revocation, MFA and privileged session controls verified.
- [ ] Audit immutability proven at database level; read access audited; retention and export tested.
- [ ] Database migrations and replica-set transactions verified on production-equivalent infrastructure.
- [ ] Clinical hazards assessed; local protocols, formulary, triage and escalation approved.
- [ ] Medication, laboratory, immunization and procedure safety workflows clinically validated.
- [ ] Finance, inventory and claims ledgers reconcile end to end.
- [ ] Offline mode, conflict resolution and downtime SOP tested.
- [ ] Backup restore, disaster recovery, incident response and monitoring drills completed.
- [ ] Data-protection registration/legal review and country approvals documented.
- [ ] Staff training, role assignment and credential verification completed.
- [ ] External integrations tested with actual counterparties; no mock is represented as live.
- [ ] Facility acceptance, release authority and rollback plan signed.

## 12. Audit conclusion

ODEI has a substantial early backend foundation and useful domain-specific workflow slices. The project is **not complete**, and the current API should be treated as a development prototype rather than an operational clinic system.

The most important immediate work is not adding more isolated endpoints. It is completing the security and governance foundation, making the existing workflows testable end to end, implementing missing read/workbench surfaces and ledgers, building the production frontend/control plane, and proving clinical and operational safety in a production-equivalent environment.

**No omission claim:** This report inventories the complete file tree returned for the reviewed `main` tree and assesses the major application, API, security, tests, docs, country profile and delivery surfaces. It is a static audit snapshot, not proof that every runtime behavior, external service, secret, deployment setting or clinical/legal obligation has been tested. Re-audit after material code changes and before any release.


## 13. Remediation changes committed after this audit snapshot

The following corrective changes have since been committed to `main`:

- OIDC JWKS cache now expires after a bounded configurable TTL (default 300 seconds; accepted setting range 30–3600 seconds), serializes refreshes and refreshes on unknown key IDs.
- Facility authorization now checks that the facility itself is active and that the role assignment's optional effective-from/effective-until dates are currently valid.
- A platform-admin-only role revocation endpoint records mandatory rationale, actor and timestamp, and writes the audit event in the same MongoDB transaction.
- Role assignment uniqueness is now limited to active assignments, preserving revoked history while permitting re-assignment.
- Readiness checks MongoDB connectivity and fetches a usable OIDC JWKS document rather than checking configuration strings only.
- Corrected the stale README implementation claims, the environment-variable example (actual settings use the `ODEI_` prefix), and the migration CLI command typo.
- CI now triggers for repository-wide changes, compiles Python sources, runs focused lint and API tests, and checks tracked files for likely secrets.
- Added tests for effective-date validation, inactive facility denial, JWKS refresh/filtering and configuration bounds.

**Verification caution:** These commits have been pushed, but their newest CI run was still pending/in progress at the time this update was written. Do not treat them as green until the latest run completes. The broader project gaps in sections 4–11 remain open.
