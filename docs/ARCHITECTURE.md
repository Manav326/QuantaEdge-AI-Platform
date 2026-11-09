# Architecture decisions

## Machine boundary

This repository is deployed only to the dedicated AI laptop. It owns model execution, knowledge retrieval, embeddings, generation, ingestion, evaluation and the public AI API. The separate application machine owns QuantaEdge web/mobile/admin services, login, identity, institution membership, course enrolment, and official learner progress.

The application backend calls `https://ai-api.quantaedge.in` over HTTPS. The hostname routes through Cloudflare to `cloudflared` running on the AI laptop, which forwards to native Windows FastAPI at `http://127.0.0.1:8000`. Ollama stays bound to `127.0.0.1:11434`; PostgreSQL and Redis Docker ports are loopback-only.

## Model and configuration boundaries

API routes call `ModelGateway`, not Ollama directly. A route selects a task policy. The task policy selects a logical model profile and prompt. The model profile selects a provider and physical model identifier. The provider adapter owns provider-specific HTTP payloads. This makes swapping Ollama for an OpenAI-compatible server or hosted provider an adapter/configuration change rather than an application rewrite.

Controls live in separate versioned files: infrastructure, providers, models, tasks, retrieval, curriculum, security and prompt files. Environment variables own machine-specific secrets and endpoints. Avoid one-off settings inside routes.

## Curriculum and data boundary

Academic metadata follows Institution → Course → Subject, then Chapter → Section → Concept. Institution/course/subject/learner identifiers are opaque references supplied by the authenticated application backend. Shared curriculum sources use a null institution_ref; institution-specific sources are only retrieved for the matching institution. The AI service does not own enrolment or official learner progress. Learner memories are institution-scoped, require explicit consent confirmation from the application backend, and are used only to personalise teaching; they are not a source of curriculum facts.

The initial vector schema uses 1,024 dimensions to match the installed Qwen3 embedding model. Embeddings from another model or dimension must never be mixed in the same vector index; a model change requires a separate index/version and re-embedding migration.

## RAG behaviour

Learning answers are filtered by curriculum, course, subject and optional chapter. Responses include source metadata and page references. In strict mode, no retrieved evidence means `insufficient_evidence`; the model is not asked to invent a textbook answer. General-model fallback is separately gated by retrieval policy and request opt-in.

## Storage

- Ollama model weights: native Windows path `D:\QuantaEdgeAI\models\ollama`.
- Docker WSL disk image: Docker Desktop-managed path `D:\QuantaEdgeAI\docker\desktop-data\DockerDesktopWSL`.
- PostgreSQL and Redis: Docker named volumes inside Docker's WSL disk image; their local host ports are bound to 127.0.0.1.
- Uploads/processed files: native API/worker paths under `D:\QuantaEdgeAI\data`.
- Source code: `D:\QuantaEdgeAI\projects\knowledge-engine`.

Do not put model weights, database volumes, document content, tunnel credentials or secrets in Git.
