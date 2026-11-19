# Hosting Provider Compatibility and Deployment Strategy

Research baseline: official provider documentation checked 19 November 2026. Product plans and APIs change; MAC must revalidate capabilities against the actual account and plan before each deployment.

## Architecture recommendation

Use provider-neutral container images and deployment contracts. Do not tie the entire ODEI system to one provider.

Suggested placement:
- Vercel: Next.js web frontend, preview deployments and compatible serverless/function workloads.
- Container-capable VPS/cloud: FastAPI core API, persistent background workers, scheduled jobs, WebSockets where needed, deployment agent and optional supporting services.
- MongoDB Atlas or an approved managed/private MongoDB deployment: operational database, with network access restricted to application workloads.
- Object storage: private clinical documents and backups, separately encrypted and access controlled.
- Independent monitoring/alerting and backup destinations.

This split avoids assuming that a frontend-focused hosting platform is automatically a full persistent application server.

## Vercel

Official documentation describes Git, CLI, Deploy Hooks and REST API deployment paths. Its API can manage deployments, domains, secrets and environment variables. Environment-variable changes apply to new deployments, not previous ones; a redeploy is required to consume the changed values. Vercel provides Local, Preview and Production environments, plus Custom Environments subject to plan availability.

Sources:
- https://vercel.com/docs/deployments
- https://vercel.com/docs/rest-api
- https://vercel.com/docs/environment-variables/managing-environment-variables
- https://vercel.com/docs/deployments/environments

Adapter policy: automate supported project, environment and deployment operations using least-privilege access tokens. Verify framework/runtime and function constraints. Do not place long-running queue workers or stateful services on Vercel merely because frontend deployment succeeds. Confirm current plan, region, function limits, networking and runtime support.

## Namecheap

Namecheap documents a cPanel Setup Python App feature. Its support article states ASGI Python applications are not supported on its Shared hosting plans and can be set up only on VPS or Dedicated Servers.

Source:
- https://www.namecheap.com/support/knowledgebase/article.aspx/10048/2182/how-to-work-with-python-app/

Adapter policy:
- Shared hosting: treat as limited/static or compatible website target only after runtime checks; do not deploy the ODEI FastAPI ASGI backend or persistent workers there.
- VPS/dedicated: candidate for API and worker containers if SSH/root, networking, storage, resource and security requirements are verified.
- Domain/DNS: manage separately through supported Namecheap APIs/account permissions; domain registration does not imply application runtime capability.
- cPanel operations may require account-specific authentication and product/API support. Where no stable supported deployment API exists, use a reviewed CI/CD or deployment-agent path, or provide a manual runbook. Never automate cPanel UI by guessing endpoints.

## Bluehost

Bluehost documentation distinguishes shared hosting from VPS/dedicated. Its current guidance states shared hosting is not positioned for persistent Node.js services, workers or server processes; VPS/dedicated provide root access and are the suitable route for such workloads. Bluehost documents Docker support on self-managed VPS and notes that self-managed environments place software/security/backup responsibilities on the customer.

Sources:
- https://www.bluehost.com/help/article/bluehost-ai-coded-pick-server-type
- https://www.bluehost.com/vps-hosting/docker
- https://www.bluehost.com/help/article/bh-hardware-full-summary
- https://www.bluehost.com/help/article/bh-what-to-expect-with-self-managed-vps

Adapter policy:
- Shared hosting: not a supported target for ODEI's persistent API/worker architecture.
- VPS/dedicated: candidate Docker/SSH target after plan, access, OS, firewall, backups and monitoring checks.
- Managed vs self-managed: record who owns patching, backups, monitoring and incident response; do not assume provider-managed operations on a self-managed VPS.

## Provider capability matrix

| Target | Web frontend | Persistent API | Background workers | Docker | MAC integration |
|---|---|---|---|---|---|
| Vercel | Strong fit | Functions/compatible runtimes; verify constraints | Not default persistent worker host | Platform-managed | REST API for supported operations |
| Namecheap shared | Plan-dependent | ASGI unsupported per cited shared-hosting guidance | Not suitable for ODEI worker architecture | Not assumed | Manual/API-limited; inspect account |
| Namecheap VPS/dedicated | Yes | Candidate | Candidate | Verify OS/plan | SSH/CI/CD or supported account APIs |
| Bluehost shared | Static/PHP and plan-dependent | Not suitable for persistent ODEI API | Not suitable | Not assumed | Limited; inspect account |
| Bluehost VPS/dedicated | Yes | Candidate | Candidate | Documented on VPS | SSH/CI/CD or provider APIs |
| Generic Docker VPS/cloud | Yes | Yes | Yes | Yes | Deployment agent/SSH API |

"Candidate" means technically plausible, not tested or connected to the user's account. MAC must run a live capability probe before deployment.

## Global provider adapter requirements

Every adapter must report: account identity, plan, region, runtimes, process model, worker support, Docker/container support, persistent storage, outbound/inbound networking, TLS, domain/DNS operations, secret management, deployment API, log access, health checks, backups, restore, usage/cost data, support ownership and known limitations.

Never claim a provider is connected until OAuth/token/SSH credentials are explicitly connected and tested. Never deploy a clinical production workload to shared hosting simply because it can serve a website.
