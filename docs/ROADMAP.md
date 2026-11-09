# Engineering roadmap

## Milestone 0 — AI server baseline

- [x] Separate AI server from QuantaEdge application services.
- [x] Keep Ollama native on Windows; do not run a second Ollama container.
- [x] Use a provider adapter and logical model profiles.
- [x] Separate infrastructure/provider/model/task/retrieval/curriculum/security/prompt configuration.
- [x] Set embedding schema to 1,024 dimensions for Qwen3 Embedding 0.6B.
- [x] Add service API key scopes and local-only API port publication.
- [x] Add Docker services for PostgreSQL/pgvector and Redis; run API and worker natively on Windows to keep Ollama loopback-only.
- [x] Add strict curriculum retrieval response and source metadata.
- [x] Add Cloudflare Tunnel deployment instructions for Windows host.

## Milestone 1 — Local integration and correctness

- [ ] Start Compose infrastructure on AI laptop and verify native API ↔ native Ollama connectivity.
- [ ] Generate separate API keys for local admin and QuantaEdge application backend.
- [ ] Verify least-privilege scope behaviour and invalid-key handling.
- [ ] Run embedding request and validate 1,024 dimensions end-to-end.
- [ ] Run generation request with task-policy settings and inspect latency/quality.
- [ ] Verify PostgreSQL migration and Redis worker health.
- [ ] Add ingestion end-to-end tests and retrieval tests with synthetic/licensed fixture data.

## Milestone 2 — Curriculum knowledge quality

- [ ] Confirm rights for NCERT commercial ingestion and derivative use before loading textbooks.
- [ ] Preserve chapter/section/page/figure/table structure and edition metadata.
- [ ] Add multilingual retrieval evaluations (English/Hindi/Urdu).
- [ ] Add hybrid vector + lexical search, reranking and citation validation.
- [ ] Add model benchmark harness for latency, accuracy and resource consumption.

## Milestone 3 — Learner context and evaluation

- [x] Add institution-scoped learner memory storage and consent-gated API CRUD.
- [x] Use stored memories only as optional teaching personalisation context.
- [ ] Add model-generated memory suggestions with application-controlled approval.
- [ ] Add mastery signals and misconception tracking using opaque learner references.
- [ ] Add golden sets, groundedness, answer quality, safety and prompt-injection tests.

## Milestone 4 — Secure public service

- [ ] Configure Cloudflare Tunnel on the AI laptop for `ai-api.quantaedge.in`.
- [ ] Add Cloudflare Access service-token policy and API-side credentials.
- [ ] Add streaming SSE, request cancellation, rate limits, quotas and usage metering.
- [ ] Add observability, alerts, backup/restore and uptime monitoring.
- [ ] Define a dedicated always-on/GPU server migration path.

## Milestone 5 — QuantaEdge integration

- [ ] Publish versioned OpenAPI contract and client integration examples.
- [ ] Integrate through QuantaEdge backend only; never place service keys in web/mobile clients.
- [ ] Preserve QuantaEdge as authority for identity, enrolments and official learner progress.
