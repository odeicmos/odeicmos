# Security and Credential Handling Baseline

## Immediate credential incident

A MongoDB database password was pasted into the project conversation. Treat it as compromised.

1. Rotate the password in MongoDB Atlas immediately.
2. Review database access, IP allowlists, users, logs and recent activity.
3. Revoke unnecessary users/tokens and use a least-privilege application user.
4. Do not reuse the exposed password or place it in GitHub, documentation, tickets or logs.
5. Store the replacement only in a managed secret store or deployment environment variable.
6. If credentials ever entered repository history, remove them from history and rotate again.

## Required controls

- Never commit secrets, patient data, private keys, production connection strings or access tokens.
- Separate development, staging and production databases and credentials.
- Restrict MongoDB network access to required application egress.
- Enforce TLS, encryption at rest, encrypted backups and tested restoration.
- Use MFA for privileged accounts, session revocation and device management.
- Enforce server-side tenant/facility/purpose authorization on every read and write.
- Log security events without passwords, tokens or unnecessary clinical payloads.
- Maintain incident response, vulnerability management, dependency scanning and penetration-test evidence.
- Require jurisdictional privacy/legal review and clinical safety approval before live deployment.

The root .env.example contains placeholders only. Never populate it with live values before committing.
