# Security model

EcoQuery is an inference proxy and audit ledger. The primary threats are a spoofed provider response, provider-key exfiltration, abuse of the inference proxy, and ledger forking or concurrent append races.

Mitigations include authenticated chat routes, identity-based rate limits, environment-only provider credentials, hashed user/org API keys, cookie-bound OAuth state, HSTS/CSP response headers, per-user ledger append locks, and full-length SHA-256 audit hashes. Behavioral verifier results are signals and are not proof of model identity.

Report vulnerabilities privately to the repository maintainers; do not include credentials or personal data in an issue.
