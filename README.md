# MyGovt — AI-Powered Citizen Intelligence & State Governance Platform

> **Your Government. Your Services. Your Voice.**
> Tamil Nadu, India — English & Tamil

---

## Overview

MyGovt is an AI-assisted platform that makes Tamil Nadu government schemes, services, documents and grievance handling easier to find and track, in English and Tamil. It is a **validated prototype, not a production service**: the seeded catalogue is *provisional* (no record is officially verified yet), real officer/authority data is not loaded, and parts of the stack have only been run locally. See [docs/audit/master_implementation_status.md](docs/audit/master_implementation_status.md) for exactly what works and what does not.

### Core Capabilities

| Capability | Description |
|---|---|
| 🏛️ **Scheme Discovery** | 12 curated TN/central schemes, each labelled with its verification status; deterministic eligibility engine (official rules not yet loaded; 8 labelled demo rules in the demo dataset) |
| 🤖 **AI Assistant** | Hybrid (keyword + vector) retrieval, passage-level citations, abstention, validated answers |
| 📋 **Complaint Management** | File, track, escalate civic complaints with SLA timelines; officers assign and progress them inside their own department |
| 🧑‍💼 **Citizen dashboard & officer console** | Role-based home pages with live counts, status charts, assignment and status updates (see [docs/demo.md](docs/demo.md)) |
| 📜 **Document Library** | Search GOs, acts, policies, and circulars |
| 🗺️ **GIS & Jurisdiction** | PostGIS point-in-polygon resolution (tested on synthetic boundaries; real boundary data not loaded) |
| 🏥 **e-Sevai Services** | 10 curated services (fees / processing times shown as *unconfirmed* until verified) |
| 🔐 **RBAC Auth** | JWT (PyJWT) + Argon2, role checks, lockout, rate limits, audit trail |
| 🗄️ **Database Architecture Explorer** | Admin-only interactive view of the real schema: architecture diagram, ER diagram, relational schema, normalization notes, example queries ([docs/database-architecture.md](docs/database-architecture.md)) |
| 🖥️ **Admin Console** | Live metrics, complaint backlog, department performance, verification queue, schema explorer, audited SQL workspace, audit logs |

---

## Technology Stack

### Backend
- **FastAPI** (Python 3.12, async) — REST API
- **PostgreSQL 16** with **PostGIS 3** (spatial) and **pgvector 0.7+** (embeddings)
- **SQLAlchemy 2.0** (async, asyncpg driver)
- **Neo4j 5** — Knowledge graph
- **Redis 7** — optional (health check only; not required by the core flows)
- **MinIO** — evidence storage is **not wired yet** (uploads are refused with 503, never silently dropped)

### Frontend
- **Next.js 15** (App Router, TypeScript)
- **Tailwind CSS** — Custom design system
- **Framer Motion** — Animations

### Infrastructure
- **Docker Compose** — 7-service local development
- **Custom PostgreSQL Dockerfile** with pgvector + PostGIS

---

## Project Structure

```
My-Govt/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/v1/            # REST endpoints
│   │   │   ├── auth.py        # Authentication & registration
│   │   │   ├── schemes.py     # Schemes + eligibility engine
│   │   │   ├── complaints.py  # Complaint management + SLA
│   │   │   ├── chat.py        # AI assistant
│   │   │   ├── gis.py         # Spatial queries
│   │   │   ├── services.py    # e-Sevai services
│   │   │   ├── documents.py   # Policy documents
│   │   │   ├── citizens.py    # Citizen profiles
│   │   │   ├── departments.py # Department directory
│   │   │   └── admin.py       # Intelligence console APIs
│   │   ├── services/          # Business logic
│   │   │   ├── auth_service.py
│   │   │   ├── scheme_service.py
│   │   │   ├── complaint_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── admin_service.py
│   │   │   └── other_services.py
│   │   ├── schemas/           # Pydantic models
│   │   ├── security/          # JWT + RBAC
│   │   ├── core/              # Config, DB, logging, health
│   │   └── jobs/              # Background scheduler (SLA escalation)
│   └── pyproject.toml
│
├── frontend/                   # Next.js application
│   └── src/app/
│       ├── page.tsx            # Hero homepage
│       ├── schemes/            # Scheme search + detail + eligibility
│       ├── services/           # e-Sevai services directory
│       ├── complaints/         # File & track complaints
│       ├── documents/          # Policy document library
│       ├── assistant/          # AI chat interface
│       └── admin/              # Intelligence console
│
├── database/
│   ├── schema/001_schema.sql   # Full database schema (60+ tables)
│   └── seeds/001_seed_data.sql # Tamil Nadu data (38 districts, 30+ schemes, 20+ services)
│
├── docker/
│   ├── postgres/               # Custom Postgres + PostGIS + pgvector
│   ├── backend/                # FastAPI container
│   └── frontend/               # Next.js container
│
└── docker-compose.yml          # 7-service orchestration
```

---

## Quick demo (university presentation)

```bash
cp .env.example .env     # set every secret
make demo                # Compose stack + labelled demonstration data (synthetic accounts, officers and complaints)
```

Open http://localhost:3000. Demo logins, a 10-minute presentation script and the list of limitations are in **[docs/demo.md](docs/demo.md)**. Demo data is synthetic and labelled; government records stay *Provisional*.

---

## Getting Started

> The Compose stack, the four application images and `make db-init / db-verify / seed-verify / demo` run in GitHub Actions
> (see [docs/audit/deployment_reproducibility_audit.md](docs/audit/deployment_reproducibility_audit.md)); the development machine
> itself has no Docker, so the Docker path has not been run locally. Locally installed PostgreSQL 16 + PostGIS + pgvector,
> Neo4j 5 and Node were used for development — see [docs/audit/final_build_validation.md](docs/audit/final_build_validation.md)
> and [docs/development.md](docs/development.md) for a setup without Docker.

### Prerequisites
- Docker Desktop 24+ (for the compose stack), Node.js 22, Python 3.12

### 1. Clone and configure

```bash
git clone https://github.com/santhoshraja-15/My-Govt.git
cd My-Govt
cp .env.example .env
# Set EVERY secret in .env — docker compose refuses to start with any secret unset (there are no defaults)
```

### 2. Start the stack and initialise the database

```bash
docker compose up -d --build
make db-init          # schema -> migrations 002..NNN -> verified seed (+ integrity checks). Clean database only.
make db-verify        # optional: replays the whole sequence in a throw-away database
```

### 3. Access the platform

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs (development only) | http://localhost:8000/api/docs |
| Citizen dashboard | http://localhost:3000/dashboard |
| Officer console | http://localhost:3000/officer (officers, department and state admins) |
| Admin console | http://localhost:3000/admin (state/system administrators only) |
| Database Architecture Explorer | http://localhost:3000/database-architecture (state/system administrators only) |

Data stores (PostgreSQL, Neo4j, Redis, MinIO) are bound to `127.0.0.1` only.

---

## Key Design Decisions

### Source-grounded answers, and what that does and does not mean
- The assistant answers only from records it retrieved (schemes, services, ingested document passages) and cites them
  with document, page and retrieval time. With no supporting source it **abstains**.
- Retrieved text is treated as untrusted data; model output is validated (citations must exist, amounts must appear in a
  source, it may never declare a person eligible) and replaced by a direct quotation of the sources if it fails.
- This reduces, but cannot eliminate, error: if a source is wrong or out of date the answer will be too. Every record shows
  its verification status so citizens can tell.

### Verification status is explicit
- `official_verified` requires a recorded document reference and is enforced by a database constraint; every change is
  logged with old status, new status, reason and time (`system.verification_status_log`).
- **At present no record is `official_verified`.** No official order text was located for any seeded record, so schemes,
  services, departments and districts are `provisional` and the UI labels them so. Fees and processing times for services
  are shown as *unconfirmed*.

### Eligibility Rule Engine
- Rules live in `schemes.eligibility_rule`; evaluation is deterministic (no ML) and missing facts give `UNKNOWN`, never a guess.
- **No scheme currently has eligibility rules recorded**, so the checker returns `INSUFFICIENT_DATA` until rules are added from official sources.

### Complaints and SLA
- Complaints route by category → department → authority. Only department-level *routing placeholders* are seeded (no real
  offices or officers); the API reports `assignment_state` honestly. Deadlines come from `complaints.sla_rule`
  (platform targets, not statutory guarantees); a scheduler escalates overdue complaints along the legal state machine.

### Data Provenance
- Seed records link to `system.source_registry`; datasets carry real SHA-256 checksums. A checksum proves file integrity,
  not that the content is correct.

---

## API Overview

```
POST /api/v1/auth/register              Register citizen          (rate limited)
POST /api/v1/auth/login                 Login (JWT)               (rate limited, 5-failure lockout)
GET  /api/v1/schemes                    List/search (verification_status filter)
POST /api/v1/schemes/{id}/eligibility   Deterministic eligibility from recorded rules
POST /api/v1/complaints                 File complaint            (signed in)
GET  /api/v1/complaints/track/{ref}     Track by reference        (public; anonymous complaints hidden)
POST /api/v1/chat/message               Source-grounded assistant
GET  /api/v1/gis/resolve-jurisdiction   Spatial lookup (needs boundary data + PostGIS)
GET  /api/v1/admin/overview             Dashboard metrics         (admin)
GET  /api/v1/admin/complaints           Backlog with legal next statuses (admin)
POST /api/v1/admin/query                Read-only SQL workspace   (system_admin; audited)
GET  /health                            State only, no internal detail
```

Complete, generated list with access rules and test coverage: [docs/audit/route_test_inventory.md](docs/audit/route_test_inventory.md).

---

## Data Sources

Seeded catalogue data comes from a curated dataset assembled from Tamil Nadu government portals (tn.gov.in, esevai,
socialwelfare, agri, tnhealth, tnschools). **It has not been verified record-by-record against official orders** — see
[docs/audit/data_provenance_assessment.md](docs/audit/data_provenance_assessment.md) and the decision register
[docs/audit/verification_decisions_2026-10-18.csv](docs/audit/verification_decisions_2026-10-18.csv). Official PDFs can be
ingested from approved sources with `make ingest` (provenance, hash and retrieval time recorded; status `unverified`).

---

## Testing

```bash
cd backend && TEST_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres TEST_POSTGIS=1 \
  TEST_NEO4J_URI=bolt://localhost:7687 TEST_NEO4J_PASSWORD=... pytest tests -q -rs     # 525 tests (16 need Neo4j)
cd frontend && npx playwright test                                                      # 103 browser tests (build with the API URL the config expects: see playwright.config.ts)
```
`TEST_ADMIN_DSN` must point at a **disposable** server (tests create/drop `mygovt_test_*` databases). Without PostGIS /
Neo4j configured the dependent tests are skipped and reported as such. Current results: [docs/audit/test_inventory.md](docs/audit/test_inventory.md).

---

## License

Government data is reproduced under the National Data Sharing and Accessibility Policy (NDSAP).
Platform code: MIT License.

---

*Built with ❤️ for Tamil Nadu citizens.*

## Policy documents, scheme/service content and Tamil/English interface

* `documents.policy_document` (migration 009, seed `003_content.sql`) holds 40 official Tamil Nadu documents (G.O.s and policies, circulars, notifications, Acts) with identifiers, issue dates and **downloaded, verified** official PDF links. Rebuild with `python etl/policy_documents/build_documents.py`, then `python etl/content/generate_seed.py`. Research notes: `docs/tamilnadu-government-document-research.md`.
* Scheme and service content (eligibility, benefits, documents, steps, fees/timelines with their provenance) is in `etl/content/`; completeness reports: `docs/scheme-data-completeness.md`, `docs/service-data-completeness.md`. All schemes and services stay *provisional*.
* The whole interface switches between English and Tamil (`frontend/src/lib/locales/`, typed so a missing Tamil string fails the build). Audit: `node frontend/audit/localization.js`; report: `docs/localization-audit.md`. The Tamil text is an unreviewed translation.
