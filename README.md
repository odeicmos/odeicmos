# ODEI Clinic OS

**OIPTECH / ODEI OS** — Global-first, MongoDB-native healthcare operating platform.

> Status: architecture and implementation baseline. This repository is not yet certified or approved for live clinical use.

## Product direction

ODEI Clinic OS coordinates patient access, longitudinal clinical care, diagnostics, medicines, immunization, finance, insurance and facility operations through governed workflows. It is designed for clinics, polyclinics, hospitals, multi-facility organizations and approved regional deployments.

### Ten first-release domains

1. Reception
2. Patient registration and identity
3. Outpatient care
4. Inpatient care
5. Pharmacy and dispensing
6. Drug procurement and inventory
7. Immunization and cold chain
8. Cash flow and accounting
9. Laboratory and diagnostics
10. Insurance and claims

Shared platform capabilities include identity, tenant/facility policy, workflow orchestration, audit, terminology, notifications, interoperability, reporting and controlled AI assistance. The ecosystem also has a privileged **Master Admin Console (MAC)** for global configuration and deployment governance, and a **Master Admin Dashboard (MAD)** for cross-ecosystem observability and management intelligence.

## Architecture baseline

- Web: Next.js, React, TypeScript and Tailwind CSS.
- API: FastAPI with typed validation and OpenAPI 3.1.
- Primary operational database: MongoDB.
- Authorization: RBAC plus contextual ABAC; server-enforced tenant and facility scope.
- Delivery: modular monolith with durable background workers and transactional outbox.
- Interoperability: pinned HL7 FHIR profiles selected per partner/country; national interfaces are versioned adapters.
- Connectivity: online-authoritative operation plus explicitly classified offline capture and reconciliation.
- Deployment: multi-tenant SaaS, dedicated organization, national/regional and self-hosted/hybrid profiles.

## Master control plane: MAC and MAD

- MAC is the privileged control plane for tenants, facilities, country profiles, environment metadata, secret references, hosting providers, deployment targets, releases, integrations, security policy and infrastructure operations.
- MAD is the read-optimized operational dashboard for ecosystem health, deployments, provider status, integration failures, security alerts, capacity and approved aggregate metrics.
- Control-plane access is separate from tenant clinical access. Global deployment authority does not grant default access to patient records.
- Secret values are write-only to the approved secret manager/provider; the application stores references and metadata, never plaintext production secrets.
- Production redeployments require MFA, policy checks, approval, immutable release plans, health verification and an auditable rollback path.
- Provider adapters must discover actual plan capabilities. Vercel, Namecheap shared hosting, Namecheap VPS, Bluehost shared hosting and Bluehost VPS are not interchangeable runtime targets.

## Non-negotiable safety and integrity rules

- No autonomous diagnosis, prescribing, emergency triage or unsupervised clinical/financial approval.
- Signed clinical content, stock movements and financial postings are corrected through attributable amendment/reversal workflows, not silent overwrite.
- Medication, vaccine, specimen, laboratory, bed, cash and claim workflows require explicit state validation and traceability.
- High-risk and online-authoritative operations require server confirmation unless a locally approved downtime protocol explicitly governs them.
- All data access is tenant/facility/purpose scoped and audited.
- Secrets are supplied at runtime; never commit credentials, tokens, production connection strings, patient data or private keys.
- No production clinical use until clinical governance, jurisdictional review, security assessment, staff training and release gates are complete.

## Repository status

This repository was empty at initial inspection. The supplied product documents define a target architecture and requirements; they do not establish that application code, integrations, validation or regulatory approvals already exist.

Implementation is planned in verified increments:

1. Governance, threat model, country profile and domain contracts.
2. Core identity, tenancy, facilities, policy and audit.
3. Patient registration, reception, appointments and queues.
4. OPD/IPD clinical workflows and nursing.
5. Procurement, inventory, pharmacy, laboratory and immunization.
6. Billing, double-entry accounting, payments and claims.
7. Offline synchronization, FHIR adapters, reporting and notifications.
8. Pilot validation, recovery drills, training and controlled release.

Each module must have automated tests, role/facility checks, audit evidence, negative tenant-isolation tests and acceptance criteria before it is described as production-ready.

## Local development

Copy `.env.example` to `.env` and provide locally managed development credentials. Never commit `.env`.

The application packages and deployment instructions will be added as implementation work is completed and tested.

## Documentation

- `docs/architecture/` — architecture decisions and domain boundaries
- `docs/security/` — threat model, access control and secure operations
- `docs/requirements/` — product requirements and acceptance criteria
- `docs/country-compliance/` — versioned jurisdiction profiles
- `docs/operations/` — deployment, backup, recovery and downtime runbooks

## License and governance

No license or regulatory certification is implied by this initial repository content. Licensing, ownership, contribution policy and release authority must be approved by OIPTECH / ODEI OS governance.


## Engineering roadmap and API scaffold

The seven approved engineering milestones and their exit gates are tracked in [the engineering roadmap](docs/operations/engineering-roadmap.md).

The first FastAPI scaffold is under `apps/api/`. It currently provides process liveness and an intentionally negative readiness response. It does **not** yet provide authentication, MongoDB persistence, authorization, audit persistence or production-ready business endpoints. Those are the first M1 implementation tasks. Install the package with:

```bash
cd apps/api
python -m pip install -e ".[dev]"
uvicorn odei_api.main:app --reload
pytest
```

The readiness endpoint must remain not-ready until dependency checks for the database, identity provider and secret manager are implemented and verified.
