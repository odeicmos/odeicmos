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
- No endpoint exposes patient records or clinical actions in this increment.
