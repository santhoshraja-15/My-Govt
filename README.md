# MyGovt — AI-Powered Citizen Intelligence & State Governance Platform

> **Your Government. Your Services. Your Voice.**
> Tamil Nadu, India — English & Tamil

---

## Overview

MyGovt is a production-grade, AI-powered platform that makes Tamil Nadu government services, schemes, and information accessible to every citizen. Built with verified government data and a zero-hallucination AI commitment.

### Core Capabilities

| Capability | Description |
|---|---|
| 🏛️ **Scheme Discovery** | 30+ TN government schemes with eligibility rule engine |
| 🤖 **AI Assistant** | Grounded RAG with trust scoring, abstention, and citation |
| 📋 **Complaint Management** | File, track, escalate civic complaints with SLA timelines |
| 📜 **Document Library** | Search GOs, acts, policies, and circulars |
| 🗺️ **GIS & Jurisdiction** | PostGIS-backed coordinate → admin boundary resolution |
| 🏥 **e-Sevai Services** | 20+ citizen services directory with fees and processing times |
| 🔐 **RBAC Auth** | JWT + Argon2 with 6-tier role hierarchy |
| 🖥️ **Admin Console** | Schema explorer, SQL workspace, data quality, audit logs |

---

## Technology Stack

### Backend
- **FastAPI** (Python 3.12, async) — REST API
- **PostgreSQL 16** with **PostGIS 3** (spatial) and **pgvector 0.7+** (embeddings)
- **SQLAlchemy 2.0** (async, asyncpg driver)
- **Neo4j 5** — Knowledge graph
- **Redis 7** — Caching and session management
- **MinIO** — Object storage for evidence files

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

## Getting Started

### Prerequisites
- Docker Desktop 24+
- Node.js 20+
- Python 3.12+

### 1. Clone and configure

```bash
git clone https://github.com/santhoshraja-15/My-Govt.git
cd My-Govt
cp .env.example .env
# Edit .env with your values
```

### 2. Start all services

```bash
docker compose up -d
```

### 3. Run database migrations and seed

```bash
# Once PostgreSQL is healthy:
docker compose exec postgres psql -U mygovt -d mygovt -f /docker-entrypoint-initdb.d/schema.sql
docker compose exec postgres psql -U mygovt -d mygovt -f /docker-entrypoint-initdb.d/seeds.sql
```

### 4. Access the platform

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Admin Console | http://localhost:3000/admin |
| MinIO Console | http://localhost:9001 |
| Neo4j Browser | http://localhost:7474 |

---

## Key Design Decisions

### Zero-Hallucination Commitment
- AI answers are grounded **only** in database content from verified government sources
- Trust score computed per response; below-threshold answers are abstained
- Every citation links back to the official government source URL

### Eligibility Rule Engine
- Rules stored in `schemes.eligibility_rule` with JSON-serializable operators
- Deterministic, fully auditable — no ML involved in eligibility decisions
- Groups support AND/OR logic; all group results combined

### SLA Management
- Complaint resolution deadlines auto-computed from `complaints.sla_rule`
- Background scheduler runs every 5 minutes to escalate overdue complaints
- Full timeline history preserved in `complaint_history`

### Data Provenance
- Every scheme, service, and document links to `system.source_registry`
- `reliability_score` (0–1) on every source drives trust computation
- Dataset registry tracks ingestion date, record count, and quality metrics

---

## API Overview

```
POST /api/v1/auth/register          Register citizen
POST /api/v1/auth/login             Login (JWT)
GET  /api/v1/schemes                List/search schemes
POST /api/v1/schemes/{id}/eligibility  Check eligibility
POST /api/v1/complaints             File complaint
GET  /api/v1/complaints/track/{ref} Track by reference
POST /api/v1/chat/message           AI assistant query
GET  /api/v1/gis/resolve-jurisdiction?lat=&lon= Spatial lookup
GET  /api/v1/admin/overview         Dashboard metrics
POST /api/v1/admin/query            Read-only SQL workspace
GET  /health                        System health
```

Full interactive docs: **http://localhost:8000/docs**

---

## Data Sources

All data is sourced from official Tamil Nadu government portals:

- **tn.gov.in** — State government portal
- **socialwelfare.tn.gov.in** — Social welfare schemes
- **agri.tn.gov.in** — Agricultural schemes
- **esevai.gov.in** — e-Sevai services catalogue
- **tnhealth.tn.gov.in** — Health schemes
- **tnschools.gov.in** — Education schemes

---

## License

Government data is reproduced under the National Data Sharing and Accessibility Policy (NDSAP).
Platform code: MIT License.

---

*Built with ❤️ for Tamil Nadu citizens.*
