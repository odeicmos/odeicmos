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
