# MyGovt — Build Instructions

Follow the phases **in order**. Each phase lists tasks, commands, deliverables and a **Definition of Done (DoD)**. Do not start the chatbot until Phases 1–4 are done.

Owners: **M1** = DB + backend, **M2** = AI + data, **M3** = frontend + integration.

---

## Phase 0 — Setup (Day 1)

### 0.1 Repository
```bash
mkdir MyGovt && cd MyGovt && git init
mkdir -p frontend backend/app/{api,models,schemas,services,repositories,ai,rag,graph,rules,gis,security,utils} \
  ai/{prompts,eval,configs} database/{schema,migrations,seeds,queries} \
  data/{raw,extracted,cleaned,validated,processed,embeddings} etl knowledge_graph gis \
  tests/{unit,integration,e2e,eval} scripts docs docker
cp ../MyGovt-docs/database/schema.sql database/schema/001_schema.sql
```
Branching: `main` (protected) ← `develop` ← `feature/<area>-<short-name>`. PRs need 1 review + green CI.

### 0.2 Docker Compose
Create `docker-compose.yml` with services:

| Service | Image / build | Notes |
|---------|---------------|-------|
| `postgres` | a PostGIS image with pgvector added (build `docker/postgres/Dockerfile` from `postgis/postgis:16-3.4` and install `postgresql-16-pgvector`) | Mount `database/schema` to `/docker-entrypoint-initdb.d` |
| `neo4j` | `neo4j:5` | Enable APOC if needed; set auth via env |
| `redis` | `redis:7` | |
| `minio` | `minio/minio` | `server /data --console-address ":9001"` |
| `backend` | `docker/backend/Dockerfile` | uvicorn, reload in dev |
| `worker` | same image | runs scheduler (SLA/escalation) |
| `frontend` | `docker/frontend/Dockerfile` | Next.js dev server |

Add health checks to all services; make `backend` depend on healthy `postgres`.

### 0.3 Tooling
- Python: `pyproject.toml` with `fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic-settings python-jose[cryptography] passlib[argon2] psycopg[binary] pgvector neo4j redis langgraph httpx sentence-transformers pytest pytest-asyncio testcontainers ruff black mypy`.
- Node: `next react typescript tailwindcss maplibre-gl @tanstack/react-query next-intl`.
- Pre-commit: ruff, black, mypy (core), eslint, prettier, detect-secrets.
- CI (GitHub Actions): lint → type-check → unit tests → integration tests (services) → migration check.

**DoD:** `docker compose up -d` brings every service healthy; `GET /health` returns OK; CI green on an empty commit.

---

## Phase 1 — Requirements, architecture, ADRs (Day 1–2)
1. Review `00_REQUIREMENTS.md` and `01_PRD.md`; freeze the MVP list (PRD §5, Priority M).
2. Write ADRs in `docs/adr/`: ADR-001 PostgreSQL system of record; ADR-002 Neo4j as projection; ADR-003 rules-before-LLM; ADR-004 embedding model; ADR-005 LLM provider; ADR-006 Tamil speech provider.
3. Choose the 30–50 seed schemes (M2) and 20–30 services (M1). Record each as a row in `docs/seed_inventory.csv` with source URL and reviewer.
4. Define the eligibility attribute registry (`backend/app/rules/attributes.py`).

**DoD:** MVP scope signed off by all three members; ADRs merged.

---

## Phase 2 — Database and GIS (Day 2–5) · M1
```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE mygovt;"
docker compose exec -T postgres psql -U postgres -d mygovt < database/schema/001_schema.sql
```
1. Verify extensions: `\dx` shows `postgis`, `vector`, `pg_trgm`, `pgcrypto`, `btree_gist`.
2. Set passwords on `mygovt_app`, `mygovt_ai_readonly`, `mygovt_etl` (`ALTER ROLE ... LOGIN PASSWORD ...`) from env, not from SQL files in git.
3. Initialise Alembic with the schema as the baseline revision; every later change is a migration.
4. Load boundaries: all districts (required), taluks (required), local bodies and wards (as available; synthetic ward polygons for the demo are acceptable and **must be labelled synthetic** in `source_registry`).
   ```bash
   ogr2ogr -f PostgreSQL PG:"dbname=mygovt user=mygovt_etl" boundaries.geojson \
     -nln staging_district -t_srs EPSG:4326 -nlt PROMOTE_TO_MULTI
   ```
   Validate: `SELECT count(*) FROM administration.district WHERE NOT ST_IsValid(geometry);` must be 0 (fix with `ST_MakeValid`).
5. Test `administration.resolve_jurisdiction(lon, lat)` for ≥ 20 known points (Coimbatore, Madurai, Chennai, border cases, a point outside TN).
6. Seed master data: state, departments (10–15), authorities with `parent_authority_id` chains, complaint categories (20–30), `routing_rule`, `sla_rule`.

**DoD:** schema applied; 20 jurisdiction tests pass; escalation chain exists for every authority except the top.

---

## Phase 3 — Data foundation and ETL (Day 3–7) · M1 + M2
1. **Source registry first.** Insert a row per source with licence and reliability score (`database/seeds/source_registry.sql`).
2. **ETL framework** (`etl/`):
   ```
   etl/
   ├── connectors/   (http, api, file, pdf, html)
   ├── extractors/
   ├── cleaners/
   ├── validators/   (pydantic models per entity)
   ├── loaders/      (idempotent upserts keyed on natural keys)
   └── run.py        (CLI: python -m etl.run --source SRC001)
   ```
   Steps per run: download → SHA-256 → store in `data/raw` (read-only) → extract → profile → clean → normalise → dedupe → validate → stage → production → quarantine failures.
3. **Loaders (MVP):** departments, schemes, eligibility rules (**human-reviewed JSON → loader**), benefits, document requirements, services/requirements, GOs, notices, laws/rules, facilities.
4. **Eligibility rules authoring:** for each seed scheme, write rules in `database/seeds/eligibility/<scheme_code>.json`:
   ```json
   {"scheme_code":"EXAMPLE-001","rules":[
     {"rule_group":1,"attribute":"age","operator":">=","value":18,"human_readable":"Applicant must be at least 18"},
     {"rule_group":1,"attribute":"gender","operator":"IN","value":["female"],"human_readable":"For women applicants"}
   ],"source_reference":"<official doc + clause>"}
   ```
   An LLM may *propose* rules from scheme text, but a human reviews every rule against the source before merge.
5. **Synthetic data generator** (`scripts/synth_data.py`, seeded RNG): 100 citizens, 100 officers, 300–1000 complaints across categories, wards and statuses (including SLA-breached ones), with Tamil/English/Tanglish text.
6. **Quality report:** compute completeness/accuracy/consistency/freshness per dataset into `dataset_registry`.

**DoD:** `make seed` is idempotent (run twice → same counts); quarantine table empty or explained; every scheme/service row has `source_id` and `verified_at`.

---

## Phase 4 — Documents, chunking, embeddings (Day 8–10) · M2
1. Extract text from PDFs (pdfplumber/PyMuPDF; OCR with Tesseract `tam+eng` only for scanned files).
2. Chunk by structure first (headings/clauses), then by size: target 300–500 tokens with ~15% overlap; keep `page_number`, `section_title`.
3. Embed with a multilingual model (e.g., BGE-M3 / multilingual-e5-large, 1024-d). Batch, store in `document_chunk.embedding`, `scheme.embedding`, `service.embedding`.
4. Create indexes after bulk load (`REINDEX` HNSW if built before load).
5. Test retrieval quality on a hand-made set of 40 queries (English, Tamil, Tanglish) → record recall@5 in `ai.evaluation_run`.

**DoD:** recall@5 ≥ 0.80 on the retrieval set; Tamil queries retrieve Tamil and English documents.

---

## Phase 5 — Hybrid search and RAG (Day 10–13) · M2
Implement in `backend/app/rag/`:
- `retriever.py` — SQL pre-filters (status, effective dates, jurisdiction), FTS, trigram, vector.
- `hybrid_search.py` — normalise each score to [0,1] (min-max per query), combine:
  `hybrid = 0.35·semantic + 0.25·keyword + 0.15·graph + 0.15·reliability + 0.10·freshness` (tune on eval set; weights are config).
- `reranker.py` — optional cross-encoder.
- `context_builder.py` — dedupe, order, token budget.
- `citation_manager.py` — assigns `[1]…[n]` markers; validates the LLM only cites supplied sources.
Hard filters are applied **before** scoring. Log every candidate to `ai.retrieval_log`.

**DoD:** 20 golden queries return the expected documents in top-5 with citations.

---

## Phase 6 — Knowledge graph (Day 13–15) · M2
1. `knowledge_graph/export.py`: read from PostgreSQL → nodes (State, District, Taluk, LocalBody, Ward, Department, Authority, Scheme, Service, Document, Policy, GO, ComplaintCategory) and relationships (CONTAINS, MANAGES, PROVIDES, ISSUES, REQUIRES, GOVERNED_BY, AVAILABLE_IN, ESCALATES_TO, HANDLES).
2. `MERGE`-based, idempotent; constraints on node IDs.
3. Cypher queries in `knowledge_graph/queries/` (schemes available in a district; documents for a scheme and which service issues them; escalation chain).
4. `make graph-rebuild` wipes and rebuilds; test node/edge counts against PostgreSQL.

**DoD:** graph counts reconcile with SQL; 3 multi-hop queries return expected results.

---

## Phase 7 — Rule engine and eligibility (Day 14–17) · M2
`backend/app/rules/`:
- `attributes.py` — registry (type, units, operators, derivation e.g. `age` from DOB at evaluation date).
- `evaluator.py` — pure functions: `evaluate_rule(rule, profile) -> PASS|FAIL|UNKNOWN`, `evaluate_scheme(rules, profile, on_date) -> SchemeResult`.
- Semantics: AND within `rule_group`, OR across groups; non-mandatory rules never cause failure; missing attribute → UNKNOWN (never FAIL).
- Output includes per-rule trace (attribute, citizen value, operator, threshold, outcome, human text).
- **Gold set:** ≥ 40 cases in `tests/unit/test_eligibility_gold.py` covering boundaries (`<=` at exactly the limit), missing data, OR-groups, date effectiveness.
- Property-based tests (hypothesis): re-ordering rules never changes the result.

**DoD:** 100% of gold cases pass; coverage ≥ 90% on the module.

---

## Phase 8 — Decision graph, policy resolver, trust layer (Day 16–19) · M2
- `policy_resolver.py` — picks the single valid version for (policy, date, jurisdiction).
- `trust_engine.py` — scores each candidate:
  ```
  source_reliability   from source_registry
  freshness            exp(-age_days / half_life) or verified_at recency
  jurisdiction_match   1.0 exact · 0.5 broader · 0.0 mismatch (hard fail)
  validity             1.0 if effective on query date else 0 (hard fail)
  consistency          agreement across independent candidates / conflict detection
  overall = weighted mean; any hard-fail item is dropped before scoring
  ```
  Abstain if overall < `TRUST_THRESHOLD` or no accepted context.
- `decision_engine.py` — writes `ai.decision` + `ai.decision_lineage` rows for every decision.
- `explanation_engine.py` — builds the LLM prompt from verified context; instructs: "Answer only from the context; cite as [n]; if insufficient, say so." Post-validates citations.
- Prompt-injection hygiene: retrieved text is wrapped as quoted data; imperative instructions inside documents are ignored.

**DoD:** adversarial tests (injection text inside a document, conflicting policies, expired policy) behave correctly.

---

## Phase 9 — FastAPI backend (Day 12–20, parallel) · M1
1. Config via `pydantic-settings`; DB sessions per request; `SET LOCAL app.role/app.citizen_id` inside the transaction.
2. Auth: register/login/refresh, argon2 hashing, JWT, RBAC dependency, lockout, rate-limits (Redis).
3. Routers per `README.md` API table; request/response Pydantic schemas; consistent error model `{code, message, details, request_id}`.
4. Services layer owns business logic; repositories own SQL; routers stay thin.
5. Audit middleware/decorator writes to `audit.audit_log` for all mutations.
6. OpenAPI examples for each endpoint.

**DoD:** integration tests pass against real Postgres; OpenAPI served; role-matrix tests prove citizens cannot read others' complaints.

---

## Phase 10 — Citizen UI (Day 16–24) · M3
Pages: Home, Ask MyGovt, Schemes (search/detail/eligibility), Services, Documents/Policies, Complaints (new / mine / detail), Profile, Government Dashboard, Admin, GIS Map.
- i18n (`next-intl`): `en`, `ta`; Tamil font Noto Sans Tamil.
- Chat UI: streaming, citation chips, trust badge, "Why this answer?" drawer (sources, rules, policy version, confidence), disclaimer.
- Eligibility UI: per-rule checklist with ✓ / ✗ / ? and "missing information" prompts.
- Accessibility: keyboard, ARIA, contrast; run axe in Playwright.

**DoD:** all MVP pages work against the real API; Lighthouse accessibility ≥ 90.

---

## Phase 11 — Complaint system (Day 18–25) · M1 + M2 + M3
1. `complaint_classifier.py` — baseline: TF-IDF + logistic regression or embedding + classifier trained on open civic datasets + synthetic Tamil/Tanglish; optional LLM few-shot for fallback. Output: category, priority, confidence.
2. `department_router.py` — deterministic `routing_rule` lookup using the resolved jurisdiction; classifier only chooses the category.
3. Officer assignment (least-loaded among active officers of the authority).
4. SLA: `due_date = created_at + sla_rule.resolution_hours`; `escalation_due_at = created_at + escalation_hours`.
5. Scheduler (`worker`): every 5 minutes, escalate eligible complaints with `FOR UPDATE SKIP LOCKED`; idempotent.
6. Evidence upload: size/MIME/magic-byte checks, SHA-256, store in MinIO; antivirus scan optional.
7. UI: submit with map pin, tracking timeline, officer queue, dashboards and heatmap.

**DoD:** routing accuracy ≥ 90% on the 100-case routing test set; overdue complaints in test data escalate exactly once.

---

## Phase 12 — Voice (Day 22–26) · M3 (+ M2)
Provider abstraction `SpeechProvider{stt(audio, lang_hint), tts(text, lang)}`. Flow: record → STT → show transcript → same pipeline → TTS. For complaints, always confirm the transcript before submission. Fall back to text if STT confidence is low.

**DoD:** 10 Tamil + 10 English voice utterances produce correct intents ≥ 80%.

---

## Phase 13 — Government and admin dashboards (Day 23–27) · M3 + M1
Cards: total, pending, in progress, resolved, SLA breached, escalated, avg resolution time; charts by department/district; heatmap from `complaint.location`; tables with filters. Admin: users, departments, authorities, officers, sources, datasets (quality scores), AI decisions (drill into lineage), audit logs.

**DoD:** dashboard numbers match SQL ground-truth queries on seeded data.

---

## Phase 14 — Testing and hardening (Day 25–29) · all
| Area | Tests |
|------|-------|
| Unit | rules, policy resolver, trust engine, routing, SLA calc, chunker |
| Integration | API + DB; RLS; migrations; ETL idempotency |
| AI eval | intent, entities, category, routing, eligibility, RAG faithfulness, Tamil set (`make eval`) |
| E2E | Playwright: register → profile → eligibility → ask → complaint → officer resolves → escalation |
| Security | authz matrix, SQLi attempts, upload abuse, JWT tampering, rate-limit, `pip-audit`, `npm audit`, OWASP ZAP baseline scan |
| Performance | k6/Locust on search and chat endpoints with seed data |
| Accessibility | axe + manual keyboard pass |

**DoD:** all acceptance criteria in `00_REQUIREMENTS.md §8` pass.

---

## Phase 15 — Deployment and demo (Day 28–30)
1. Production-like compose (`docker-compose.prod.yml`): no reload, HTTPS reverse proxy (Caddy/Nginx), secrets via env files outside git.
2. Backups: nightly `pg_dump`; document restore.
3. Seed a clean demo database; freeze data version.
4. **Demo script (≈10 min):**
   1. Home → language switch Tamil/English.
   2. Ask: "I am a 23-year-old woman from Coimbatore. What schemes can I apply for?" → show eligible/near-miss/insufficient data, citations, **Why this answer?**
   3. Change income above a limit → show deterministic NOT_ELIGIBLE with the failing rule.
   4. Ask "I want an income certificate" → service, fee, documents, link.
   5. Voice complaint in Tamil about a street light → confirm transcript → complaint ID, jurisdiction, authority, SLA.
   6. Officer dashboard → open complaint → update.
   7. Fast-forward time on a breached complaint → auto-escalation → timeline shows it.
   8. Admin → AI decision lineage + audit log + source registry.
   9. Adversarial question (outdated policy / out-of-scope weather) → abstain / refuse.
5. Record a backup screen-capture of the demo.

---

## Cross-cutting rules (apply from day 1)
1. **No LLM-generated SQL.** The LLM calls no tools that write.
2. **Raw data immutable.**
3. **Every PR** updates tests and, if behaviour changes, docs.
4. **Every schema change** is a migration.
5. **Secrets** never in git.
6. **Synthetic data only**; label it.
7. **Time zone:** store UTC, display IST.
8. **Config over constants:** thresholds, weights, SLA hours in config/DB.

## Suggested Makefile targets
```make
up: ; docker compose up -d --build
down: ; docker compose down
migrate: ; docker compose exec backend alembic upgrade head
seed: ; docker compose exec backend python -m scripts.seed
embed: ; docker compose exec backend python -m app.rag.embeddings --all
graph-rebuild: ; docker compose exec backend python -m knowledge_graph.rebuild
test: ; docker compose exec backend pytest -q --cov=app
eval: ; docker compose exec backend python -m ai.eval.run_all
e2e: ; cd frontend && npx playwright test
lint: ; ruff check . && black --check . && mypy backend/app && (cd frontend && npm run lint && npx tsc --noEmit)
scheduler: ; docker compose exec worker python -m app.jobs.sla_once
```

## Troubleshooting
| Symptom | Likely cause / fix |
|---------|--------------------|
| `type "vector" does not exist` | pgvector missing in image; rebuild Postgres image |
| `ST_Contains` returns nothing | SRID mismatch or invalid polygons; run `ST_MakeValid`, ensure 4326 |
| HNSW build very slow | Build after bulk load; raise `maintenance_work_mem` |
| Neo4j auth failure | Reset `NEO4J_AUTH` volume or password |
| RLS hides all rows | Missing `SET LOCAL app.role/app.citizen_id` in the transaction |
| Tamil text garbled | Ensure UTF-8 DB encoding and font in UI/PDF extraction |
