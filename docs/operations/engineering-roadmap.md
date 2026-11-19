# ODEI Clinic Management OS — Engineering Roadmap

Status: implementation plan; all release gates remain subject to review and evidence.

## Delivery principles

- Build the global architecture and Uganda pilot profile together; do not fork the product into separate codebases.
- Keep the MAC/MAD control plane separate from tenant clinical data and clinical authorization.
- Deliver a modular monolith first: Next.js/TypeScript web, FastAPI/Python API, MongoDB operational store, durable workers and provider adapters.
- Treat all consequential actions as authenticated, authorized, tenant/facility-scoped, validated, idempotent where appropriate and auditable.
- No production credentials, connection strings, patient data or private keys in Git.
- A milestone is complete only when code, automated tests, security evidence, operational documentation and acceptance evidence exist.

## Milestones and exit gates

### M1 — MAC/MAD backend foundation
Scope:
- Authentication integration boundary (OIDC), MFA policy for privileged operators, session lifecycle and recovery controls.
- RBAC plus contextual ABAC; deny-by-default permissions; tenant and facility scoping on every API request.
- Control-plane API, organization/facility registry, MongoDB configuration registry and append-only audit service.
- Separate MAC command APIs from MAD read models.
Exit gate:
- Login/session tests; authorization matrix tests; cross-tenant and cross-facility negative tests; audit completeness tests; database indexes/validation reviewed.
- No default clinical-record permission for platform operators.

### M2 — Environment and secrets management
Scope:
- Secret-manager adapter interface and provider-backed implementation; application stores secret references and metadata only.
- Versioned configuration sets, schema validation, environment scopes, immutable change history, approvals and rollback.
- Redaction in logs, API responses, errors and audit payloads.
Exit gate:
- Secret values never returned after write; no plaintext secrets in MongoDB or logs; rotation and failed-approval tests; config diff and rollback evidence.

### M3 — Deployment orchestration
Scope:
- Immutable release plan, policy checks, approval, deployment job state machine, health verification and rollback.
- Vercel adapter; generic Docker VPS adapter; Namecheap and Bluehost account-specific adapters only after plan/API capability verification.
- Provider credentials scoped to a deployment agent and least privilege.
Exit gate:
- Dry-run and sandbox tests; idempotent retries; cancellation/timeouts; failure recovery; no production deploy without explicit approval.

### M4 — Multi-facility healthcare network
Scope:
- Tenant and organization provisioning; facility hierarchy; country profile registry and approval lifecycle.
- Shared identity with facility-scoped assignments; contextual authorization; isolation and data residency controls.
Exit gate:
- Tenant isolation tests; facility access matrix; country profile versioning and effective-date tests; audited provisioning/deprovisioning.

### M5 — Healthcare operational MVP
Scope:
- Registration, reception, OPD, pharmacy, laboratory, immunization and finance workflows.
- Preserve the broader ten-domain first-release blueprint, including IPD, procurement and insurance/claims, as planned release scope.
Exit gate:
- End-to-end synthetic-data tests; clinical workflow review; medication/specimen/vaccine traceability; financial reconciliation; downtime and sync tests; no autonomous clinical decisions.

### M6 — MAD intelligence
Scope:
- Read-optimized projections for service health, deployment status, security alerts, infrastructure capacity and approved aggregate operational reporting.
- Source freshness, metric definitions, alert ownership and drill-down authorization.
Exit gate:
- Metric correctness tests; stale-data indicators; alert routing tests; access controls; no patient-level detail in global views by default.

### M7 — Uganda pilot and global readiness
Scope:
- Uganda country profile and facility-specific configuration; regulatory and professional review; integration and acceptance testing; synthetic-data testing; training, backup/restore and incident drills.
- Global readiness through jurisdiction-specific profiles and documented localization/validation.
Exit gate:
- Written legal/privacy and clinical governance sign-off; security assessment; data-protection and hosting review; facility acceptance; restore drill; controlled release authorization.

## Parallel workstreams

- Architecture/specification: maintain ADRs, API contracts, data dictionary, threat model and country profile templates.
- Engineering: deliver executable slices behind feature flags and test gates.
- Validation: synthetic fixtures, role matrix, isolation tests, usability review and operational drills.
- Governance: named owners for clinical, privacy, security, finance and release approvals.

## Current implementation status

The repository contains the architecture baseline, MAC/MAD requirements and an interactive frontend prototype. These are not a production backend. M1 begins with the backend scaffold and then adds persistence, identity, policy and audit in independently testable increments. No provider account is considered connected until an authorized connection has been established and verified.
