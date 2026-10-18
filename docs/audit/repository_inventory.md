# MyGovt Repository & Data Architecture Inventory

## Executive Overview
The **MyGovt** platform is designed as an AI-powered Citizen Intelligence and State Governance Platform dedicated to the state of Tamil Nadu, India. This document establishes an immutable baseline inventory of the repository components, seeded datasets, and data models prior to verification remediation.

## Repository Component Breakdown
| Directory | Subcomponents | Primary Technologies | Audit State |
|---|---|---|---|
| `database/` | `schema/001_schema.sql`, `seeds/001_seed_data.sql`, `migrations/` | PostgreSQL 16, PostGIS 3, pgvector 0.7+ | Inspected; 17 schema/data discrepancies identified |
| `backend/` | `app/api`, `app/models`, `app/services`, `app/core` | FastAPI, SQLAlchemy, Pydantic, Python 3.11 | Inspected; relies on PostgreSQL & pgvector |
| `frontend/` | `src/app`, `src/components`, `src/lib` | Next.js 14, React, TailwindCSS, Lucide Icons | Inspected; interfaces with citizen services |
| `scripts/` | `discovery/`, `comparison/`, `reporting/` | Python 3.11 stdlib automation | Operational audit automation suite created |
| `data/` | `raw/official/`, `cleaned/`, `extracted/`, `validated/` | JSON, GeoJSON, Metadata Sha256 | Structured; official raw datasets ingested |
| `metadata/` | `verification_reports/` | JSON audit logs, catalog records | Machine-readable discrepancy & source catalogs |
| `docs/` | `adr/`, `audit/` | Markdown specifications | Architecture decision records & 9 audit reports |

## Seeded Data Records Breakdown
- **Source Registry**: 7 seed records in `001_seed_data.sql` (audited; expanded to 13 in `002_verified_seed_data.sql`).
- **States**: 1 record (`TN` - Tamil Nadu).
- **Districts**: 38 administrative districts (identified 4 code duplicate collisions, 1 Maharashtra name error 'Thane').
- **Departments**: 15 key secretariat & commissionerate departments.
- **Complaint Categories**: 10 primary civic & administrative grievance categories.
- **SLA Rules**: 10 default operational turnaround rules.
- **Government Schemes**: 30 seeded schemes (identified PM-Kisan as Central sector scheme needing explicit jurisdictional reclassification).
- **Citizen Services**: 20 e-Sevai revenue and vital statistics services.
- **Dataset Registry**: 3 synthetic entries with unproven 1.0 quality scores; corrected with genuine SHA256 checksums and provenance metadata.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
