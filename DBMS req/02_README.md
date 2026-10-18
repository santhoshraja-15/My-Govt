# MyGovt

**AI-Powered Citizen Intelligence & State Governance Platform** — *Your Government. Your Services. Your Voice.*

MyGovt helps Tamil Nadu citizens discover government schemes and services, check eligibility, search official documents, and file and track civic complaints — through one text/voice interface in Tamil and English.

> **Design rule:** the LLM is never the source of truth.
> Official data → database → retrieval → deterministic rules → verification → AI explanation → action → audit.

> ⚠️ **Prototype disclaimer.** MyGovt is an academic prototype. It is not an official government portal. All citizen, officer and complaint data are **synthetic**. Information may be outdated; always confirm on the official website.

---

## Features
- Scheme discovery with **deterministic eligibility** (`ELIGIBLE` / `NOT_ELIGIBLE` / `INSUFFICIENT_DATA`) and per-rule explanations
- Service finder (fees, documents, processing time, official route)
- Search over Government Orders, notices, laws, policies (version-aware)
- Conversational assistant ("Ask MyGovt") with citations, trust score and a **"Why this answer?"** panel
- Complaint filing with auto-classification, **PostGIS jurisdiction resolution**, deterministic routing, SLA tracking and **auto-escalation**
- Officer and department dashboards, admin console, audit log
- Tamil / English / Tanglish; voice input and output (stretch)

## Architecture at a glance
```
Next.js UI ─► FastAPI (auth · RBAC) ─┬─► Application services
                                     └─► LangGraph orchestrator
                                              │
                          Hybrid retrieval (SQL · FTS · pgvector · Neo4j)
                                              │
                  Rules / policy resolver ─► Trust layer ─► LLM ─► Actionability gate ─► Audit
PostgreSQL (+PostGIS, pgvector)   Neo4j (derived)   Redis   MinIO
```
See `docs/04_FLOW_DOCUMENT.md` for full diagrams.

## Tech stack
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, TypeScript, Tailwind CSS, MapLibre/Leaflet |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 |
| AI | LangGraph, pluggable LLM, multilingual embeddings (1024-d), STT/TTS provider abstraction |
| Data | PostgreSQL 16, PostGIS 3, pgvector, Neo4j 5, Redis, MinIO |
| Quality | pytest, Playwright, ruff, black, mypy, eslint, prettier |
| Ops | Docker Compose, GitHub Actions |

## Repository layout
```
MyGovt/
├── frontend/            Next.js app
├── backend/             FastAPI app (api, services, repositories, rules, gis, security, ai, rag, graph)
├── ai/                  Prompts, eval sets, model configs, notebooks
├── database/            schema/, migrations/, seeds/, queries/
├── data/                raw/ extracted/ cleaned/ validated/ processed/ embeddings/   (raw is immutable)
├── etl/                 Source connectors, validators, loaders
├── knowledge_graph/     Neo4j export/import + Cypher
├── gis/                 Boundary files, loaders
├── tests/               unit/ integration/ e2e/ eval/
├── scripts/             seed, rebuild-graph, synth-data
├── docs/                PRD, SRS, flows, build docs, ADRs
├── docker/              Dockerfiles, compose overrides
├── .env.example
├── docker-compose.yml
├── Makefile
└── README.md
```

## Prerequisites
- Docker 24+ and Docker Compose v2
- Python 3.11+, Node.js 20+ (for local, non-Docker development)
- An LLM API key (or a local model endpoint) — optional for non-AI features
- ~8 GB RAM recommended (Neo4j + Postgres + embedding model)

## Quick start
```bash
git clone <repo-url> MyGovt && cd MyGovt
cp .env.example .env               # fill in secrets
docker compose up -d --build       # postgres, neo4j, redis, minio, backend, frontend, worker
make migrate                       # apply database/schema.sql / Alembic migrations
make seed                          # departments, districts, schemes, services, synthetic data
make embed                         # chunk + embed documents and schemes
make graph-rebuild                 # project PostgreSQL → Neo4j
open http://localhost:3000         # UI      (API docs: http://localhost:8000/docs)
```

### Demo accounts (synthetic, created by `make seed`)
| Role | Email | Password |
|------|-------|----------|
| Citizen | citizen1@example.test | set in `.env` (`DEMO_PASSWORD`) |
| Officer | officer1@example.test | same |
| Department admin | deptadmin@example.test | same |
| State admin | stateadmin@example.test | same |

## Configuration (`.env.example`)
```
# Database
POSTGRES_HOST=postgres  POSTGRES_PORT=5432  POSTGRES_DB=mygovt
APP_DB_USER=mygovt_app  APP_DB_PASSWORD=change-me
AI_DB_USER=mygovt_ai_readonly  AI_DB_PASSWORD=change-me
ETL_DB_USER=mygovt_etl  ETL_DB_PASSWORD=change-me
# Graph / cache / storage
NEO4J_URI=bolt://neo4j:7687  NEO4J_USER=neo4j  NEO4J_PASSWORD=change-me
REDIS_URL=redis://redis:6379/0
MINIO_ENDPOINT=minio:9000  MINIO_ACCESS_KEY=change-me  MINIO_SECRET_KEY=change-me
# Security
JWT_SECRET=change-me  JWT_ACCESS_MINUTES=15  JWT_REFRESH_DAYS=7
# AI
LLM_PROVIDER=...  LLM_MODEL=...  LLM_API_KEY=...
EMBEDDING_MODEL=...  EMBEDDING_DIM=1024
TRUST_THRESHOLD=0.70  CLASSIFIER_CONFIDENCE_THRESHOLD=0.60
STT_PROVIDER=...  TTS_PROVIDER=...
# App
DEFAULT_LANGUAGE=en  ALLOWED_ORIGINS=http://localhost:3000
DEMO_PASSWORD=change-me
```
Never commit `.env`. Use a secret manager outside local development.

## Common commands
| Command | Description |
|---------|-------------|
| `make up` / `make down` | Start / stop services |
| `make migrate` | Apply DB migrations |
| `make seed` | Load seed + synthetic data |
| `make etl SOURCE=<code>` | Run an ETL job for one registered source |
| `make embed` | (Re)build embeddings |
| `make graph-rebuild` | Rebuild Neo4j from PostgreSQL |
| `make test` | Unit + integration tests |
| `make eval` | AI evaluation suites |
| `make e2e` | Playwright end-to-end tests |
| `make lint` | ruff, black --check, mypy, eslint, tsc |
| `make scheduler` | Run SLA/escalation worker once |

## API overview (`/api/v1`)
| Area | Endpoints |
|------|-----------|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh` |
| Schemes | `GET /schemes`, `GET /schemes/{id}`, `POST /schemes/check-eligibility`, `GET /schemes/recommended` |
| Services | `GET /services`, `GET /services/{id}`, `GET /services/search` |
| Documents | `GET /documents`, `GET /documents/{id}`, `GET /documents/search` |
| Complaints | `POST /complaints`, `GET /complaints`, `GET /complaints/{id}`, `PATCH /complaints/{id}/status`, `POST /complaints/{id}/evidence`, `POST /complaints/{id}/escalate` |
| AI | `POST /ai/chat`, `/ai/voice`, `/ai/eligibility`, `/ai/classify-complaint`, `GET /ai/decisions/{id}` |
| GIS | `GET /gis/jurisdiction`, `/gis/districts`, `/gis/taluks`, `/gis/local-bodies` |
| System | `GET /health` |
Interactive docs at `/docs` (OpenAPI).

## Data sources
Data comes from three tiers — **official** (TN OGD, e-Sevai, GO portal, India Code, MyScheme, IGOD, district portals), **trusted open** (Hugging Face / GitHub / OSM-derived), and **synthetic** (citizens, officers, complaints). Each source is registered in `system.source_registry` with a licence and reliability score. Re-verify availability and licence of any dataset before loading it. See `docs/00_REQUIREMENTS.md §5`.

## Testing
```bash
make test        # pytest: unit + integration (Postgres/Neo4j via Testcontainers or compose)
make eval        # intent, entity, routing, eligibility, RAG faithfulness, Tamil suites
make e2e         # Playwright
```
Targets: ≥70% coverage overall, ≥90% on `rules/`, `policy`, `routing`.

## Security notes
- JWT + RBAC; argon2id/bcrypt password hashing; rate limiting
- Separate DB roles; AI role is read-only on knowledge tables only
- LLM never receives DB credentials and never runs SQL/Cypher
- Append-only audit log
- Synthetic data only; no Aadhaar or ID numbers stored

## Documentation index
| File | Purpose |
|------|---------|
| `00_REQUIREMENTS.md` | Software requirements specification |
| `01_PRD.md` | Product requirements |
| `03_DATABASE_SCHEMA.md` + `database/schema.sql` | Schema design + DDL |
| `04_FLOW_DOCUMENT.md` | Flows and sequence diagrams |
| `05_BUILD_INSTRUCTIONS.md` | Step-by-step build guide |
| `06_BUILD_PROMPT.md` | Phase prompts for AI coding assistants |
| `07_PROJECT_CONTROL.md` | Plan, RACI, risks, quality gates |
| `08_TECHNICAL_DEEP_DIVE_MASTER_PROMPT.md` | Full technical master prompt |

## Team
| Role | Focus |
|------|-------|
| Member 1 | Database, PostGIS, ETL, FastAPI, auth, complaint & service APIs |
| Member 2 | Data, RAG, pgvector, Neo4j, eligibility, trust layer, NLP, evaluation |
| Member 3 | Next.js UI, dashboards, GIS map, voice, integration, E2E testing |

## Licence and attribution
Choose a licence for the code (e.g., MIT). Datasets keep their own licences — see `source_registry.license`.
