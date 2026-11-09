# Security model and release gates

## Deployment trust boundary

- Only the FastAPI gateway is reachable through Cloudflare Tunnel.
- Docker publishes the API only on host loopback (`127.0.0.1:8000`).
- Ollama listens on the AI laptop and is called by the API/worker over Docker Desktop's host gateway. Never create a public tunnel or router port for 11434.
- PostgreSQL and Redis are private Docker-network services; no host ports are published.
- Application backends authenticate with distinct, high-entropy `X-API-Key` credentials and least-privilege scopes. Keep credentials in host environment/secret storage, never in browser or Android bundles.
- Cloudflare Access service authentication is an additional ingress control, not a replacement for API authentication.

## Public repository rules

This is a public source repository. Never commit `.env`, API keys, Cloudflare tunnel credentials, model weights, database files, learner records, uploaded documents, backups or licensed textbook material. `.gitignore` excludes local runtime data. Review every commit before pushing.

## Data and curriculum rights

The ingestion API rejects `pending_review` and `unknown` rights statuses. Allowed values are technical attestations only; they do not establish legal rights. Before ingesting NCERT or any third-party material for a commercial learning product, obtain and retain the applicable written permission/licence for storage, extraction, embedding, retrieval, display and generated derivatives. Do not commit textbooks or extracted content to this repository.

## Required before production

1. Replace development API keys and database credentials; use a managed secret store and rotation procedure.
2. Add key issuance, hashing-at-rest, rotation, revocation and per-client rate limits/quotas.
3. Configure Cloudflare Access service tokens and restrict the public hostname to approved service callers.
4. Add request-size limits, malware scanning, MIME/signature checks, parser isolation and upload throttling.
5. Add database row-level security or explicit namespace/tenant isolation for multi-institution data, plus adversarial isolation tests.
6. Define learner-memory consent, retention, export and deletion. Treat learner identifiers as opaque references; do not send unnecessary PII to the AI service.
7. Add evaluation suites for answer correctness, retrieval recall, citation precision, multilingual quality, prompt injection and safety.
8. Add structured audit events, metrics, tracing, alerting, backup restore tests and disaster recovery.
9. Review model licences and provider data-processing terms before production use.
10. Keep a verified sleep/uptime policy and monitor availability; a laptop is not a high-availability production host.

The initial implementation is a development baseline, not a security certification. Do not serve real learner or confidential data until the applicable release gates are implemented and tested.
