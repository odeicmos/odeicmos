# Control-plane bootstrap and deployment runbook

## Prerequisites

- Python 3.12.
- MongoDB deployment configured as a replica set or Atlas cluster; the API uses transactions to atomically persist registry writes and their audit events.
- Dedicated MongoDB application user with only required application privileges. Audit collection writer must be denied update and delete privileges. Migration identity is separate from runtime identity.
- OIDC issuer configured with RS256 signing keys, issuer, audience and JWKS endpoint.
- TLS termination, private network path to MongoDB, restricted ingress and a deployment secret manager.

## Local development

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
# Inject ODEI_MONGODB_URI and ODEI_OIDC_* values through your local secret mechanism.
uvicorn odei_api.main:app --reload
pytest -q
ruff check src tests
```

Do not use production data or credentials in local development.

## Readiness

- `GET /health/live` means only that the process responds.
- `GET /health/ready` verifies MongoDB connectivity, the applied baseline schema marker, and a usable configured OIDC JWKS document. It does not verify workers, object storage, secrets-provider health, or external integrations.
- Identity configuration is independently required for protected control-plane routes.
- No route should be considered production-ready until authorization, audit grants, tenant isolation and operational tests pass.

## Initial platform administrator

The first platform administrator must be provisioned through the selected identity provider's controlled administrator workflow. Its verified access token must contain the explicitly governed `odei_platform_roles: ["platform_admin"]` claim. Do not add an unauthenticated bootstrap endpoint or seed a default password.

## Database migrations

Run the currently implemented baseline index/schema migration using a separately authorized migration identity before starting the API. From `apps/api/`, install the package (`python -m pip install -e .`) and execute `odei-migrate` with `ODEI_MONGODB_URI` injected by the secret manager. The command applies the idempotent baseline index set and records schema marker `2026.11.27.1` only after all index operations succeed. Never run migrations automatically on every API process startup. This is not yet a general ordered migration framework with checksums, locking, rollback, or drift remediation.

## Registry API

All routes are under `/api/v1/control-plane` and require verified OIDC bearer tokens plus the platform_admin claim:
- POST `/tenants`
- POST `/organizations`
- POST `/facilities`
- POST `/role-assignments`

Registry writes and audit events use a MongoDB transaction. The database must support transactions. The tenant must exist before an organization can be created; the organization must exist before a facility can be created.

## Rollback and recovery

Registry mutations are not deleted to roll back a provisioning error. Use a reviewed, audited status transition or compensating action. Restore procedures must be rehearsed against isolated backups before production approval.
