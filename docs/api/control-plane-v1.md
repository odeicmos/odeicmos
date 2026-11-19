# Control-plane API v1 — initial contract

Base path: `/api/v1`  
Authentication: OIDC bearer access token; RS256 verification against configured issuer JWKS; exact issuer and audience validation; exp/iat/iss/aud/sub required.  
Global mutation authorization: verified token claim `odei_platform_roles` must include `platform_admin`.  
Content type: JSON. Unknown request properties are rejected.

## Health

- `GET /health/live`: process liveness only.
- `GET /health/ready`: returns 503 unless MongoDB and OIDC configuration are present and MongoDB ping succeeds. This is not a full dependency, queue or downstream integration health check.

## Platform registry

All endpoints below require platform administrator authentication.

### POST /control-plane/tenants

Request:
```json
{
  "tenant_id": "tenant_example",
  "name": "Example Health Network",
  "deployment_model": "multi_tenant_saas",
  "country_code": "UG"
}
```
Creates an active tenant. Duplicate IDs return 409.

### POST /control-plane/organizations

Request:
```json
{
  "tenant_id": "tenant_example",
  "organization_id": "org_example",
  "name": "Example Health Network",
  "legal_name": "Example Health Network Ltd",
  "country_code": "UG"
}
```
Requires an existing active tenant. Duplicate tenant/organization keys return 409.

### POST /control-plane/facilities

Request:
```json
{
  "tenant_id": "tenant_example",
  "organization_id": "org_example",
  "facility_id": "facility_kampala_01",
  "name": "Example Clinic",
  "facility_type": "clinic",
  "country_code": "UG"
}
```
Requires an existing active organization in the same tenant.

### POST /control-plane/role-assignments

Request:
```json
{
  "tenant_id": "tenant_example",
  "facility_id": "facility_kampala_01",
  "user_id": "oidc-subject",
  "user_issuer": "https://identity.example.org/",
  "role": "clinician"
}
```
Requires an existing active facility. Initial supported roles: facility_admin, clinician, nurse, pharmacist, lab_scientist, vaccinator, receptionist, finance_officer, procurement_officer, claims_officer, auditor and read_only.

## Transaction and audit behavior

Each registry insert and its audit event are written in one MongoDB transaction. Use a transaction-capable replica set or Atlas deployment. Audit collection permissions must deny update and delete to the application writer. A separate migration identity applies indexes.

## Known limitations — not production-complete

- OIDC JWKS retrieval currently uses an in-process cache without a configured TTL or distributed cache.
- The first release uses a platform-admin claim for registry mutations; tenant-scoped delegated administration and facility-role authorization middleware remain to be implemented.
- Role assignments are provisioned, but user self-service, approval/expiry/revocation workflows and access-review campaigns are not implemented.
- No production identity provider has been connected or tested.
- No MongoDB instance has been connected or tested by this repository change.
- Patient registration/read and the initial encounter, clinical-note and care-plan workflows are available; specialty workflows, full EMR, clinical decision support and production validation remain incomplete.


## Identity and facility authorization hardening

Role assignments identify a user by the pair `user_issuer` and `user_id` (OIDC issuer plus subject); the subject alone is not globally unique. The unique assignment index includes tenant, issuer, subject, facility, and role. The API security module now exposes `authorize_facility_access`, which fails closed unless an active assignment matches the authenticated issuer, subject, tenant, facility, and one of the caller's allowed roles. Clinical and operational route handlers must call this policy before accessing facility-scoped data; the existence of a role assignment does not itself grant access to every API.

The verifier rejects non-RS256 algorithms, requires standard identity claims, refreshes JWKS once when a key identifier is not found, and distinguishes identity-provider/JWKS unavailability (503) from invalid credentials (401). JWKS is still cached only in process memory without a bounded TTL; production deployment must add a bounded cache and operational key-rotation monitoring.

**Migration note:** existing role-assignment records must be backfilled with the correct trusted OIDC issuer before enabling issuer-scoped authorization. Do not infer an issuer from a user-supplied value. Apply the revised index through a controlled migration after reviewing existing index definitions and duplicate records.


## Patient registration API (initial facility workflow)

### `POST /api/v1/patients`

Requires a verified OIDC bearer token and an active facility role of `facility_admin`, `clinician`, `nurse`, or `receptionist`. The request includes tenant and facility scope, a facility medical-record number, legal name, and optional preferred name, date of birth, sex-at-birth marker, phone number, and preferred language. Unknown fields are rejected. The medical-record number is unique within a tenant/facility pair. The write and its audit event are committed in one MongoDB transaction.

### `GET /api/v1/patients/{patient_id}?tenant_id=...&facility_id=...`

Requires an active facility role of `facility_admin`, `clinician`, `nurse`, `receptionist`, `auditor`, or `read_only`. The query is constrained by patient, tenant, facility, and active record status. A read audit event is appended.

This is the first registration slice, not a complete electronic medical record. It intentionally does not yet implement duplicate-patient matching, merge workflows, consent/legal-basis records, guardianship, encounter documentation, clinical notes, diagnosis, allergies, medication history, MPI across facilities, patient self-service, or offline registration. Those require separate domain workflows, governance and tests. Production use also requires MongoDB replica-set transaction support, database-level least privilege, encryption/key management, backup verification and approved clinical/privacy processes.


## Clinical workflow API — initial slice

All endpoints require a verified OIDC bearer token and an active facility assignment. All identifiers and queries are scoped by tenant and facility; the API does not permit cross-facility patient or encounter lookup.

### `POST /api/v1/clinical/encounters`

Creates an open OPD, emergency, inpatient, procedure, immunization or telehealth encounter for an active patient in the same facility. Roles: facility_admin, clinician, nurse, receptionist. Priority is routine, urgent or emergency. The encounter and audit event are written transactionally.

### `POST /api/v1/clinical/notes`

Adds a bounded clinical note to an open encounter. Note types: assessment, progress, nursing, discharge or procedure. Roles: facility_admin, clinician, nurse. The initial implementation marks submitted notes signed and records the authenticated author; amendments, co-signatures, templates, terminology validation and signature policy are not yet implemented. Do not treat this as a validated medico-legal documentation workflow.

### `POST /api/v1/clinical/care-plans`

Creates an active patient care plan with a title, one or more goals, one or more interventions, and an optional review due date and encounter link. Roles: facility_admin, clinician, nurse. Care-plan versioning, task assignment, outcome tracking, review/closure and patient-facing sharing remain future work.

These endpoints are an initial API foundation only. They do not implement triage, admission/discharge/transfer, bed management, medication orders, laboratory orders, results, immunization schedules, billing, claims, procurement, inventory, offline synchronization or FHIR exchange. Clinical governance must approve the note-signing semantics and specialty workflows before live use.


## Pharmacy API — initial ordering and dispensing slice

### `POST /api/v1/pharmacy/orders`

Requires facility_admin or clinician. Creates a pending medication order for an active patient and open encounter in the same facility. Each line requires a medication code, display name, dose, route, frequency and positive quantity; duration and instructions are optional. The order and audit event are transactional.

### `POST /api/v1/pharmacy/orders/{order_id}/dispense`

Requires facility_admin or pharmacist. Dispenses a pending order by allocating unexpired active stock lots in first-expiry-first-out (FEFO) order. Every lot decrement, order state transition, dispensing event and audit event occur in one MongoDB transaction. If any line cannot be fully supplied, the transaction is aborted; the order remains pending and stock decrements roll back.

**Inventory lot contract:** dispensing expects `inventory_lots` documents to contain tenant_id, facility_id, medication_code, lot_id, batch_number, expiry_at, received_at, quantity_on_hand and status. Lot intake, stock adjustments, returns, quarantine, recalls, controlled medicines, unit conversions and cycle counts are not implemented in this slice.

**Clinical safety limitation:** this is not yet a safe-to-deploy prescribing/dispensing system. Allergy and interaction checking, medication reconciliation, formulary controls, weight/renal/hepatic dosing, duplicate therapy, pregnancy checks, controlled-drug governance, pharmacist clinical verification, partial dispensing, substitutions, patient counselling, label generation and adverse-event reporting are not implemented. Do not use these endpoints for live patient care until those controls and clinical validation are complete.


## Laboratory API — initial order/specimen/result lifecycle

### `POST /api/v1/laboratory/orders`

Requires facility_admin or clinician. Creates a laboratory order linked to an active patient and open encounter in the same facility. Tests are supplied as a bounded list of local test codes/names and priority is routine, urgent or stat. The order is stored as `awaiting_specimen` and audited transactionally.

### `POST /api/v1/laboratory/orders/{order_id}/specimens`

Requires facility_admin, nurse or lab_scientist. Records one specimen against an order awaiting collection, including specimen type, optional container and collection site. The order transitions to `specimen_collected`. A unique order/specimen index prevents duplicate collection records.

### `POST /api/v1/laboratory/orders/{order_id}/results`

Requires facility_admin or lab_scientist. Records a preliminary result for an order with a collected specimen, including analyte, value, optional unit/reference range, interpretation and comment. Result and audit records are written transactionally.

**Not yet implemented:** barcode labels, multiple specimen containers per order, accessioning, rejection/recollection, chain-of-custody events, analyzer/LIS integrations, validated test catalogue and units, reference-range rules by age/sex/pregnancy, delta checks, critical-result escalation/acknowledgement, pathologist verification, amended/final results, microbiology workflows, quality control, external lab referrals and FHIR DiagnosticReport/Observation exchange. Preliminary results must not be treated as verified clinical results.


## Immunization API — administration and adverse-event reporting

### `POST /api/v1/immunization/administrations`

Requires facility_admin, vaccinator or nurse. Records a vaccine administration for an active patient in the facility, including vaccine code/name, dose number, administration time, batch, expiry, quantity and route. An optional encounter must belong to the same patient and facility. The API rejects future administration times and batches expired at the recorded administration time. Administration and audit records are transactional.

### `POST /api/v1/immunization/adverse-events`

Requires facility_admin, vaccinator, nurse or clinician. Records an adverse event associated with an immunization record, with description, severity, optional onset and outcome. The report and audit event are transactional.

**Not yet implemented:** schedule/forecast engine, age- and risk-based eligibility, contraindication screening, dose interval validation, catch-up schedules, defaulter tracing, consent, cold-chain sensors and excursion management, stock issue/reconciliation, national DHIS2/HMIS submission, regulator reporting adapters, AEFI causality review and workflow, investigation/closure, and FHIR Immunization/AdverseEvent interoperability. This API records reported facts; it does not determine vaccine eligibility or clinical suitability.
