# Security Notes (Hosted Compute)

## Early posture (recommended)
- No arbitrary user code on hosted workers (initially).
- Only allow validated JobSpec + asset uploads with limits.
- Controlled runtime image pinned by digest.
- Strict quotas: runtime, output size, concurrency.
- Tenant isolation at storage namespace; stronger isolation for enterprise later.

## Common risks
- malicious assets / parsers
- cost abuse
- tenant data leakage
- supply chain risks in container images
