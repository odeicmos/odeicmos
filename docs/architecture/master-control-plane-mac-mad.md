# Master Admin Console (MAC) and Master Admin Dashboard (MAD)

## 1. Status and authority

MAC and MAD are first-class ODEI Clinic Management OS products. MAC is the ecosystem's privileged control plane; MAD is its operational observability and management-intelligence plane. They are not ordinary facility admin pages.

The control plane governs platform configuration and infrastructure. It does not replace clinical governance or authorize clinical acts. Clinical decisions, prescriptions, result validation, dispensing, immunization and financial approvals remain subject to facility roles, professional scope and workflow controls.

## 2. Product distinction

### MAC — Master Admin Console

A secure, privileged workspace to configure, provision, operate and govern:
- global platform settings and feature flags;
- tenant, organization, legal entity, country, region and facility provisioning;
- user identity federation, role templates, privileged access and support access;
- environment configuration and deployment targets;
- hosting provider connections and deployment profiles;
- application releases, build artifacts, promotion, rollback and maintenance windows;
- database, storage, queues, email/SMS, payment, FHIR and other integration configuration;
- domains, DNS instructions, certificates and routing configuration;
- backup/restore policy, retention, disaster recovery and data residency;
- security policies, audit review, vulnerability status and incident response;
- subscription/entitlement and platform-level usage controls, where commercially enabled.

### MAD — Master Admin Dashboard

A read-optimized view of:
- ecosystem availability and service health;
- tenant/facility onboarding and active status;
- deployment inventory, versions, build and release status;
- provider/region health, resource use and cost estimates;
- queue depth, worker health, database latency and backup freshness;
- integration connectivity and synchronization failures;
- security alerts, access anomalies and open incidents;
- aggregate operational usage and approved financial summaries;
- rollout progress, failed checks, maintenance and change calendar.

MAD must clearly distinguish measured telemetry, derived estimates, delayed metrics and unavailable data. A green status must never be shown when health checks are stale or absent.

## 3. Control-plane topology

Separate the control plane from the healthcare data plane:
- Control plane: MAC UI, MAD UI, control-plane API, policy engine, deployment orchestrator, provider adapters, secret-manager integration, configuration registry, release registry and control-plane audit.
- Data plane: tenant/facility application instances, clinical and administrative APIs, MongoDB data, object storage, event workers and facility integrations.

The control plane should not routinely read patient records. Support access to tenant data is exceptional, purpose-bound, time-limited, approved, minimized and audited. Global operators must not gain implicit access to clinical content merely because they can deploy software.

## 4. Environment variable management

MAC provides a structured environment-variable manager with:
- application/project/service and deployment target scope;
- environment scope: development, test, preview, staging, production and facility-specific where necessary;
- variable name, type, owner, purpose, classification, version and rotation date;
- values stored only in an external secret manager or provider secret store;
- write-only secret input and masked metadata; no plaintext read-back;
- validation, references, expiry/rotation reminders and dependency mapping;
- staged changes, approval, change diff (names/metadata only), deploy plan and confirmation;
- deployment/redeployment status, health checks and rollback guidance;
- audit trail for create/update/delete/rotation and deployment action.

Public/non-sensitive configuration may be visible to authorized operators. Secret values must never be stored in application MongoDB, ordinary config tables, logs, analytics, browser storage, Git, build artifacts or audit payloads. Store secret references and metadata only. Encrypt transport and use KMS-backed envelope encryption where the selected secret manager supports it. Provider APIs may return secret values only on write; MAC must not promise read-back.

Never expose server secrets through NEXT_PUBLIC variables or browser bundles. Separate preview/staging/production credentials and restrict production secret administration to dedicated privileged roles with MFA and approval.

Environment updates do not necessarily change already running deployments. The orchestrator must understand each provider's propagation behavior and explicitly create/redeploy a new release where required. Do not report a variable as active until the target deployment has picked up the intended version and passed verification.

## 5. Deployment orchestration

A deployment target records provider, account reference, region/zone, project/server, runtime capability, environment, domain, source repository, branch/commit, artifact digest, configuration version, secret references, health checks, backup/restore policy and owner.

Deployment workflow:
1. User selects tenant/platform target, provider, environment, release and change request.
2. Policy engine checks role, MFA, approvals, maintenance window and blast radius.
3. Capability adapter validates that target supports required runtimes, containers, networking, persistent processes, workers, storage and database connectivity.
4. Generate immutable deployment plan with exact source commit, artifact digest, config revision and target.
5. Run tests, dependency/security scans, schema/migration compatibility and backup preflight.
6. Show human-readable plan, changes, risks, expected downtime and rollback method.
7. Obtain explicit approval for production or high-risk changes.
8. Execute with idempotency key; stream provider job state and logs with secrets redacted.
9. Run smoke, readiness, dependency and tenant-isolation checks.
10. Promote traffic only after policy gates pass.
11. Verify deployment and environment configuration versions; monitor error/latency/clinical workflow signals.
12. Record immutable audit evidence and release metadata.
13. On failure, stop promotion and execute only the pre-approved safe rollback; data migrations require backward-compatible expand/contract patterns and cannot be naively reversed.

MAC must support scheduled and manual redeployment, staged rollout, canary/blue-green where supported, rollback to known artifact, maintenance mode and deployment freeze. Do not execute shell commands from user-supplied strings. Provider credentials must be scoped, short-lived where possible and revocable.

## 6. Provider adapter contract

Provider adapters implement a common interface:
- validate_connection / inspect_account;
- list_projects_or_servers;
- discover_capabilities;
- validate_deployment_plan;
- configure_domains_or_return_dns_instructions;
- configure_environment_secrets;
- build_or_upload_artifact;
- deploy / redeploy / promote / rollback;
- deployment_status / logs / health;
- usage_and_cost_estimate where API supports it;
- backup_status / restore where provider integration supports it.

Every capability is explicit: supported, partial, manual-required or unsupported. No UI promise that all hosting plans offer the same controls.

Initial adapters:
- Vercel: API-driven project/deployment/environment operations for compatible frontend and function workloads.
- Namecheap: domain/DNS and account operations where supported; hosting deployment varies by product. cPanel/shared plans have restrictions; VPS/dedicated deployment can use SSH/agent or CI/CD. Verify account/product/API permissions before enabling.
- Bluehost: VPS/dedicated Docker/SSH deployment is a candidate; shared hosting is not a target for persistent API/worker services. Verify plan and access before enabling.
- Generic Docker/SSH target: self-managed VPS/dedicated infrastructure with pinned deployment agent, SSH certificate or short-lived credentials.
- Future adapters: AWS, Azure, Google Cloud, DigitalOcean, Hetzner, Render, Railway and other providers after capability and security review.

MAC may orchestrate providers; it does not bypass their account permissions, terms, API limitations or product constraints.

## 7. Security model

Use separate control-plane identity and data-plane tenant authorization. Require MFA, step-up authentication and dual approval for production secrets, destructive infrastructure operations, cross-tenant changes, restore, key rotation and global release promotion.

Roles include Platform Owner, Platform Security Administrator, Release Manager, Infrastructure Operator, Auditor and Read-only Executive. Separate duties: an operator can prepare a release without approving their own production promotion. Facility/tenant admins cannot enter global control plane by virtue of facility admin role.

All actions are policy-checked server-side. Record actor, role, purpose, target, before/after metadata, approval chain, source, correlation ID, timestamp, result and provider job ID. Never record secret values. Support access is just-in-time, time-bound, tenant-scoped and logged.

Protect MAC with private access controls, rate limits, CSRF/session protections, IP/device policy where appropriate, break-glass procedures and emergency revocation. The control plane is a critical concentration of risk and needs its own threat model, penetration testing, backup and disaster recovery.

## 8. MAD metrics and alerting

Every metric has source, timestamp, freshness SLA, aggregation scope and quality state. Do not mix tenant metrics or display patient-identifiable information on global dashboards. Aggregation requires privacy policy and minimum cohort controls. Clinical quality metrics require clinical owner and approved definitions.

## 9. Acceptance criteria

- No plaintext secret is returned after save or exposed in browser/client logs.
- Production deployment requires MFA and configured approval policy.
- Tenant/facility operators cannot access global controls.
- A provider with missing capability is blocked with a clear explanation.
- Deployment plan pins source commit and artifact digest.
- Environment changes trigger provider-appropriate redeployment and version verification.
- Failed health checks prevent promotion.
- Rollback preserves audit and data integrity.
- Control-plane audit events cannot be modified by ordinary platform operators.
- MAD indicates stale/unknown telemetry honestly.
- Control plane has independent backup, restore and incident exercises.
