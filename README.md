# QuantaEdge AI Platform

Standalone, API-first AI server for QuantaEdge and other authorised applications. This repository runs on the **dedicated AI laptop**. The QuantaEdge website, Android backend, authentication, institution/course enrolment and official learner progress stay on the separate application machine.

## Machine boundary

- **This AI laptop:** native Windows FastAPI gateway, ARQ ingestion worker, native Ollama, PostgreSQL + pgvector and Redis (the latter two in Docker), knowledge retrieval, model registry and Cloudflare Tunnel connector.
- **Other machine:** QuantaEdge web/mobile/admin applications and business database. Its backend calls `https://ai-api.quantaedge.in` over HTTPS.
- **Not in Git:** model weights, Docker Desktop WSL virtual disk, database volumes, Redis data, uploaded documents, licensed NCERT files, secrets or backups.

The API listens on `127.0.0.1:8000`. Cloudflare Tunnel on this same AI laptop forwards `ai-api.quantaedge.in` to that local address. Ollama listens on `127.0.0.1:11434` and is never exposed to the LAN or internet.

## Architecture

```mermaid
flowchart TB
  APP[QuantaEdge backend on application machine]
  CF[Cloudflare edge: ai-api.quantaedge.in]
  TUN[cloudflared on AI laptop]
  API[Native Windows FastAPI :8000]
  SEC[API authentication / scopes]
  ROUTE[Task router and policy layers]
  KNOW[Knowledge retrieval]
  EMB[Embedding profile]
  CHAT[Generation profile]
  DB[(PostgreSQL + pgvector in Docker)]
  REDIS[(Redis in Docker)]
  WORK[Native Windows ARQ worker]
  OLLAMA[Native Windows Ollama :11434]
  APP -->|HTTPS + service credential| CF --> TUN --> API
  API --> SEC --> ROUTE
  ROUTE --> KNOW --> DB
  ROUTE --> EMB --> OLLAMA
  ROUTE --> CHAT --> OLLAMA
  API --> REDIS --> WORK
  WORK --> OLLAMA
  WORK --> DB
```

Running the API and worker natively on Windows is intentional: they can call Ollama through loopback without binding the unauthenticated Ollama API to a network interface. Docker Desktop runs only PostgreSQL and Redis, with host ports bound to loopback.

## Layered configuration

Behaviour is controlled by separate files under `config/`; route code must not contain one-off model settings.

| Layer | Owns |
|---|---|
| `infrastructure.yaml` | service limits, timeouts, worker and storage defaults |
| `providers.yaml` | provider endpoints and capabilities |
| `models.yaml` | logical model profiles, physical model IDs, capabilities and embedding dimensions |
| `tasks.yaml` | task-to-model routing, prompts and inference parameters |
| `retrieval.yaml` | chunking, top-k, filters and score thresholds |
| `curriculum.yaml` | curriculum catalogue and academic hierarchy |
| `security.yaml` | API scopes, upload rights gate and network policy |
| `prompts/` | versioned task prompts, separate from route code |

Machine-specific secrets and paths belong in the ignored `.env` file. Restart the API/worker after changing YAML configuration; configuration is loaded once per process.

## Initial local model profiles

The initial profiles match models installed on this AI laptop:

- `qwen3-embedding-0.6b` → `qwen3-embedding:0.6b` → **1,024 dimensions**.
- `qwen3.5-teacher-2b` → `qwen3.5:2b-q4_K_M` → text generation.

These are development candidates, not certified teaching models. Inference parameters including `think`, temperature, context and output limits are set in `config/tasks.yaml`. The API sends the task policy to the provider adapter; applications do not select raw Ollama tags. Image/vision APIs are not yet implemented, so the 2B profile is advertised as text-chat only.

## Windows storage layout

Expected workspace root: `D:\QuantaEdgeAI`

```text
D:\QuantaEdgeAI\
├── projects\knowledge-engine\       # clone this repository here
├── models\ollama\                   # native Ollama weights (not Git)
├── data\uploads\                    # originals (not Git)
├── data\processed\                  # extracted text / page assets (not Git)
├── data\temporary\                  # temporary work (not Git)
├── docker\desktop-data\             # Docker-managed WSL virtual disk (not Git)
├── logs\                              # runtime logs (not Git)
└── backups\                           # backups (not Git)
```

PostgreSQL and Redis use Docker named volumes inside Docker Desktop's WSL disk image, whose location is configured in Docker Desktop as `D:\QuantaEdgeAI\docker\desktop-data\DockerDesktopWSL`. The pre-created `data\postgres` and `data\redis` folders are reserved and are not used by the current named-volume configuration.

## Prerequisites

- Windows 11, WSL 2 and Docker Desktop using the WSL 2 engine. Ubuntu is not required.
- Python **3.12**. Install with `winget install --id Python.Python.3.12 -e --source winget`, then reopen PowerShell.
- Ollama for Windows with the model profiles above; `OLLAMA_MODELS` should point to `D:\QuantaEdgeAI\models\ollama`.
- Git for Windows and GitHub CLI for source control.
- Keep the laptop awake and online while the public API is expected to respond.

## First-time setup on the AI laptop

Clone this repository into `D:\QuantaEdgeAI\projects\knowledge-engine`, then from PowerShell:

```powershell
cd D:\QuantaEdgeAI\projects\knowledge-engine
.\scripts\initialize.ps1
```

The script creates a Python 3.12 virtual environment, installs dependencies and generates a local `.env` with random database and API credentials if one does not already exist. Keep `.env` private. Store the printed `quantaedge-backend` key in the application backend's secret manager.

Start database infrastructure:

```powershell
.\scripts\start-infrastructure.ps1
```

Run migrations:

```powershell
.\scripts\migrate.ps1
```

Open a separate PowerShell terminal and start the API:

```powershell
.\scripts\start-api.ps1
```

Open another terminal and start the ingestion worker:

```powershell
.\scripts\start-worker.ps1
```

Check local services:

```powershell
.\scripts\check.ps1
```

Local API docs: `http://127.0.0.1:8000/docs`. API liveness: `http://127.0.0.1:8000/health`. Authenticated readiness: `http://127.0.0.1:8000/ready`.

## API contract overview

All application endpoints use `/v1`. Requests require `X-API-Key`; issue distinct least-privilege credentials to each server-side consumer. Never embed the key in React or Android.

| Method | Path | Purpose | Scope |
|---|---|---|---|
| GET | `/health` | Liveness only | Public |
| GET | `/ready` | Database, Redis and Ollama readiness | `admin:read` |
| GET | `/v1/models` | Enabled logical profiles | `models:read` |
| POST | `/v1/chat/completions` | General AI chat | `chat` |
| POST | `/v1/embeddings` | Embeddings | `embeddings` |
| POST | `/v1/learning/answers` | Curriculum-filtered grounded answer | `learning` |
| POST | `/v1/knowledge/documents` | Upload and queue authorised material | `knowledge:write` |
| GET | `/v1/knowledge/documents/{id}` | Ingestion status | `knowledge:read` |

The application machine remains authoritative for learner identity, institution membership, enrolment and official progress. The AI service accepts opaque `learner_ref` and optional `institution_ref` values from the authenticated application backend. Shared curriculum documents have no `institution_ref`; institution-specific documents are restricted to their matching institution.

## Cloudflare Tunnel

Install `cloudflared` natively on Windows and configure `ai-api.quantaedge.in` to route to `http://localhost:8000`. See [`ops/cloudflared/README.md`](ops/cloudflared/README.md). The tunnel connector runs on the AI laptop, not on the application machine. Never tunnel Ollama (11434), PostgreSQL (5432) or Redis (6379).

## Curriculum and rights boundary

The repository contains curriculum metadata and ingestion code, not NCERT books or extracted textbook passages. Ingest a source only after the intended use is covered by documented rights, including storage, extraction, embedding, retrieval, display and generated derivatives. The API's rights attestation is a technical gate, not legal verification.

## Current scope and release status

This is an initial development baseline: API gateway, logical model routing, Ollama provider, 1,024-dimension embedding schema, knowledge ingestion queue, curriculum-filtered vector retrieval, source metadata, scoped API keys and Windows lifecycle scripts. Learner memory lifecycle, hybrid search, reranking, vision ingestion, full evaluation suite, rate limiting, streaming SSE and production observability remain planned work. Do not use real learner or confidential data until the security release gates in `SECURITY.md` are implemented and reviewed.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m compileall apps\api\app apps\api\alembic
.\.venv\Scripts\python.exe -m pytest apps\api\tests -q
```

## License

MIT applies to original code in this repository only. It does not grant rights to third-party model weights, textbooks or datasets.
