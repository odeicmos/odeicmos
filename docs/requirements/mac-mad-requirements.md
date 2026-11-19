# MAC and MAD — Product Requirements

## Purpose

Deliver the ODEI Clinic OS global control plane and its monitoring counterpart.

## MAC navigation domains

1. Global Overview and Control Center
2. Organizations, Tenants and Facilities
3. Countries, Regions and Jurisdiction Profiles
4. Users, Roles, Privileged Access and MFA
5. Applications, Projects and Environments
6. Environment Variables and Secret References
7. Hosting Providers and Account Connections
8. Deployment Targets and Runtime Capabilities
9. Releases, Build Artifacts, Redeployments and Rollbacks
10. Domains, DNS, TLS and Routing
11. Databases, Storage, Queues and Backups
12. Integrations: FHIR, HL7, HMIS, laboratories, insurers, payments, SMS and email
13. Feature Flags and Configuration Versions
14. Security Policies, Audit and Incident Management
15. Monitoring, Alerts and Maintenance Windows
16. Subscriptions, Entitlements and Usage (if enabled)
17. Documentation, Runbooks and Support Operations

## MAD navigation domains

1. Ecosystem health
2. Tenant/facility network map and status
3. Deployments and release versions
4. Infrastructure and provider health
5. Database, worker, queue and storage health
6. Integration and synchronization health
7. Security and audit alerts
8. Availability, performance and capacity trends
9. Aggregate service utilization
10. Incident timeline and change calendar

## Functional requirements

- Every resource has a stable ID, owner, scope, status, version and audit history.
- Global configuration is versioned and can be promoted through dev/test/staging/prod.
- Secrets are write-only and represented by secret-manager references.
- Provider credentials are connected explicitly, tested, scoped and revocable.
- Capability discovery precedes deployment.
- Deployment plans show immutable commit and artifact digest, config revision, impact and rollback.
- Production changes require policy-based approval and MFA.
- Redeployment is idempotent, observable and verifiable.
- Tenant/facility boundaries are enforced independently of UI visibility.
- MAD metrics display source, timestamp, freshness and unknown state.
- Support access is time-limited, purpose-bound and audited.
- High-risk actions have confirmation, approval and recovery procedure.

## First MVP acceptance

1. MAC login with MFA-ready role model and seeded local development roles.
2. Dashboard shell and navigation for MAC/MAD.
3. Organization/tenant/facility registry with sample synthetic data.
4. Environment registry and safe variable metadata UI; secret values never rendered after save.
5. Provider registry for Vercel, Namecheap, Bluehost and Generic Docker VPS.
6. Capability matrix and deployment-plan preview using mock adapters.
7. Audit event list for every configuration/deployment action.
8. MAD overview with explicit demo/mock telemetry labels.
9. No real deployment until a provider connection is explicitly configured and a production approval policy is active.
10. Automated tests for role denial, tenant isolation, secret redaction and deployment state transitions.

## Explicit non-goals for first MVP

- No automatic purchase of hosting plans or domains.
- No storing provider root passwords or unrestricted cloud keys.
- No direct shell execution from the browser.
- No automatic production redeploy from an unreviewed environment edit.
- No unrestricted access to patient clinical records from MAC/MAD.
- No false claim of live provider connectivity or infrastructure monitoring.
