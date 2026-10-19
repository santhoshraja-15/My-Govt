# Developer guide

Everything here describes behaviour that was actually run on this repository unless marked **(not run)**.
Evidence and exact outputs: [audit/final_build_validation.md](audit/final_build_validation.md).

## 1. Architecture

```
 Browser (Next.js 15, TypeScript, EN/தமிழ்)
      │  REST/JSON + JWT (access 15 min, refresh 7 d; stored in localStorage)
      ▼
 FastAPI (async)  ── security: JWT, roles, ownership checks, rate limits, lockout, headers, audit trail
      │   services: schemes · services · complaints (+rules) · chat/RAG · admin · citizens · gis
      ▼
 PostgreSQL 16 ── PostGIS (jurisdiction, facilities) · pgvector (embeddings) · pg_trgm
      ▲                         ▲                       ▲
      │ etl.pipeline            │ app.ai.embeddings.run │ knowledge_graph.rebuild ──► Neo4j 5 (optional projection)
 official PDFs (allow-listed)   local BGE / OpenAI      (PostgreSQL stays the source of truth)
```

Schemas: `system` (sources, datasets, verification log, ingestion log) · `administration` · `identity` · `schemes` ·
`services` · `policies` · `documents` · `complaints` · `ai` (decisions, lineage) · `audit` (append-only, trigger-protected).

Neo4j, Redis and MinIO are **optional**: no core flow requires them. The graph is rebuilt from PostgreSQL on demand.

## 2. Database initialisation (order matters)

| Step | File | Re-runnable |
|---|---|---|
| 1 | `database/schema/001_schema.sql` | No – clean database only |
| 2 | `database/migrations/002_provenance_and_audit_fixes.sql` | Yes |
| 3 | `003_api_schema_alignment.sql` – complaint address, profile attributes | Yes |
| 4 | `004_verification_governance.sql` – status log, `official_verified ⇒ source_document_ref`, defaults | Yes |
| 5 | `005_spatial_fixes_postgis.sql` – **needs PostGIS** (`ST_Covers`, deterministic pick, geography index) | Yes |
| 6 | `006_routing_authority_model.sql` – routing placeholders provenance | Yes |
| 7 | `007_synthetic_data_flags.sql` – `is_synthetic` + `@synthetic.invalid` constraint | Yes |
| 8 | `008_ingestion_tracking.sql` – retrieval/extraction/embedding tracking, `ingestion_log` | Yes |
| 9 | `database/seeds/002_verified_seed_data.sql` via `python -m scripts.seed` | Yes (idempotent) |

`database/seeds/001_seed_data.sql` is a **legacy, unaudited** seed and is never applied.
`make db-init` runs the sequence; `python -m scripts.db_verify --admin-dsn …` replays it in a disposable database and
probes constraints. `scripts.seed` exit codes: 0 ok · 1 a check failed (seed rolled back) · 2 preflight failed (schema/migration missing);
`--dry-run` rolls back, `--verify-only` reports without repairing, `--strict` fails on warnings. Alembic has no revisions
(SQL files are the source of truth); `make migrate` says so.

## 3. Running locally without Docker

PostgreSQL 16 with PostGIS and pgvector (on Windows the OSGeo `postgis-bundle` zip can be unpacked into a conda
`postgresql` environment; Linux: the project's `docker/postgres` image or distro packages), then:

```bash
cd backend && pip install -r requirements-ci.txt          # test/runtime subset, exact versions
export POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_USER=postgres POSTGRES_PASSWORD=… POSTGRES_DB=mygovt_dev
# apply 001, then 002…008 (psql -v ON_ERROR_STOP=1 -f …) then:
python -m scripts.seed
uvicorn app.main:app --port 8000
cd ../frontend && npm ci && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build && npx next start
```
Full local ML dependencies (torch, sentence-transformers) are only needed for `EMBEDDING_PROVIDER=local`.

## 4. Environment variables

Generated from `app/core/config.py` (secrets are never defaulted in `docker-compose.yml`). In `APP_ENV=production` the API refuses to
start with placeholder secrets.

| Variable | Default |
|---|---|
| `APP_ENV` | `'development'` |
| `APP_LOG_LEVEL` | `'INFO'` |
| `APP_DEBUG` | `True` |
| `APP_CORS_ORIGINS` | `'http://localhost:3000'` |
| `FRONTEND_URL` | `'http://localhost:3000'` |
| `POSTGRES_HOST` | `'postgres'` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `'mygovt'` |
| `POSTGRES_USER` | `'postgres'` |
| `POSTGRES_PASSWORD` | *(secret – must be set in .env)* |
| `MYGOVT_APP_PASSWORD` | *(secret – must be set in .env)* |
| `NEO4J_URI` | `'bolt://neo4j:7687'` |
| `NEO4J_USER` | `'neo4j'` |
| `NEO4J_PASSWORD` | *(secret – must be set in .env)* |
| `REDIS_URL` | `'redis://redis:6379/0'` |
| `MINIO_ENDPOINT` | `'minio:9000'` |
| `MINIO_ACCESS_KEY` | *(secret – must be set in .env)* |
| `MINIO_SECRET_KEY` | *(secret – must be set in .env)* |
| `MINIO_BUCKET_EVIDENCE` | `'mygovt-evidence'` |
| `MINIO_BUCKET_DOCUMENTS` | `'mygovt-documents'` |
| `JWT_SECRET_KEY` | *(secret – must be set in .env)* |
| `JWT_ALGORITHM` | `'HS256'` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `LLM_PROVIDER` | `'none'` |
| `LLM_API_KEY` | `''` |
| `LLM_MODEL` | `'gpt-4o-mini'` |
| `LLM_MAX_TOKENS` | `2048` |
| `LLM_TEMPERATURE` | `0.1` |
| `EMBEDDING_PROVIDER` | `'local'` |
| `EMBEDDING_MODEL` | `'BAAI/bge-large-en-v1.5'` |
| `EMBEDDING_API_KEY` | `''` |
| `EMBEDDING_DIMENSION` | `1024` |
| `EMBEDDING_BATCH_SIZE` | `32` |
| `TRUST_THRESHOLD` | `0.7` |
| `CLASSIFIER_CONFIDENCE_THRESHOLD` | `0.6` |
| `HYBRID_WEIGHT_SEMANTIC` | `0.35` |
| `HYBRID_WEIGHT_KEYWORD` | `0.25` |
| `HYBRID_WEIGHT_GRAPH` | `0.15` |
| `HYBRID_WEIGHT_RELIABILITY` | `0.15` |
| `HYBRID_WEIGHT_FRESHNESS` | `0.1` |
| `MAX_RETRIEVAL_CHUNKS` | `50` |
| `RETRIEVAL_MIN_SIMILARITY` | `0.5` |
| `MAX_CONTEXT_TOKENS` | `6000` |
| `RATE_LIMIT_LOGIN_PER_MIN` | `10` |
| `RATE_LIMIT_REGISTER_PER_HOUR` | `5` |
| `RATE_LIMIT_CHAT_PER_MIN` | `30` |
| `FEATURE_VOICE` | `False` |
| `FEATURE_GRAPH` | `True` |
| `FEATURE_VECTOR_SEARCH` | `True` |

Also read directly: `TEST_ADMIN_DSN`, `TEST_POSTGIS`, `TEST_NEO4J_URI|USER|PASSWORD` (tests), `GRAPH_PSEUDONYM_SECRET`
(graph export of citizen pseudonyms; empty = none exported), `E2E_PG_*` (Playwright), `VALIDATED_DATA_DIR`, `SEED_DIR`.

## 5. Authentication and authorisation

* Roles (`identity.app_user.role`): `citizen`, `officer`, `department_admin`, `state_admin`, `system_admin`, plus service roles.
* Citizens can read only their own complaints, conversations and decisions (ownership checks; proven by tests).
* Admin endpoints: `state_admin`/`system_admin`; the SQL workspace is `system_admin` only, read-only, audited; complaint status
  changes: `officer`/`department_admin`/`state_admin`.
* Login: Argon2 hashes, 5 failures ⇒ 15-minute lockout (generic 401), 10 logins/min and 5 registrations/h per IP (**in-process**
  limits: with several workers the effective limit multiplies; use a shared store for strict limits).
* Every sensitive action writes `audit.audit_log` (actor, action, entity, outcome, request id, IP) – never passwords, tokens,
  e-mail addresses or profile values.

## 6. Verification statuses

`official_verified` · `externally_referenced` (central/other authority, e.g. PM-Kisan) · `provisional` · `unverified` (ingested
documents: origin is official, content not verified) · `deprecated` (terminal). The synthetic marker is separate (`is_synthetic`).
`official_verified` needs a non-empty `source_document_ref` (database CHECK) – the CHECK proves a reference *exists*, **not that
anyone checked it**; promotions must go through a reviewed change plus a logged reason. All changes land in `system.verification_status_log`.

## 7. Pipelines

| Task | Command | Notes |
|---|---|---|
| Ingest official PDFs | `python -m etl.pipeline --dsn … --source TN_GOV_PORTAL --page https://www.tn.gov.in/ --limit 5` | allow-list from `source_registry`, robots.txt, hash dedupe, supersede on change, per-stage log |
| Embed | `python -m app.ai.embeddings.run --all` | model + text-hash tracked; dimension validated against the column (never truncated) |
| Evaluate retrieval | `python -m ai.eval.run_all --provider local` | 13 golden questions; re-tune `RETRIEVAL_MIN_SIMILARITY` when the model/corpus changes |
| Rebuild graph | `GRAPH_PSEUDONYM_SECRET=… python -m knowledge_graph.rebuild` | idempotent; previous graph kept on failure |
| Synthetic data | `python -m scripts.synth_data --dsn …/mygovt_dev --seed 42` | refuses any database not named `mygovt_test*/dev*/synth*` |
| One SLA pass | `python -m app.jobs.sla_once` | the scheduler runs the same logic every 5 min |

## 8. Tests and quality gates

```bash
cd backend && ruff check app scripts etl knowledge_graph ai tests && mypy app scripts etl knowledge_graph ai
TEST_ADMIN_DSN=… TEST_POSTGIS=1 TEST_NEO4J_URI=… TEST_NEO4J_PASSWORD=… pytest tests -q -rs --cov
cd ../frontend && npx tsc --noEmit && npx next lint && npm run build && npx playwright test
```
Coverage must be configured for greenlets (`[tool.coverage.run] concurrency`) – without it SQLAlchemy-async code is reported as uncovered.
Inventories (generated): [audit/test_inventory.md](audit/test_inventory.md), [audit/route_test_inventory.md](audit/route_test_inventory.md).

## 9. Deployment notes (read before going live)

`docker-compose.yml` is a **development** stack (dev servers, hot reload, source mounts). Production still needs: secrets from a
secret manager, TLS and a reverse proxy, a production image build for both services (no `--reload`, non-root user), pinned
image tags (MinIO uses `latest`), backups/restore procedures, shared rate-limit storage, log shipping, and a real deployment
review. None of this has been done or validated.

## 10. Troubleshooting

| Symptom | Cause |
|---|---|
| `seed` exits 2 "preflight FAILED" | schema or a migration is missing – apply `001`, then every `00N_*.sql` |
| spatial tests skipped "BLOCKED" | no PostGIS / `TEST_POSTGIS=1` not set |
| complaint has `assignment_state: department_level` | expected: only routing placeholders exist; real district/taluk authorities must be loaded from official sources |
| assistant abstains although a record exists | similarity below `RETRIEVAL_MIN_SIMILARITY`, or embeddings not generated (the response says so in `evidence_notes`) |
| ingestion `stored_empty` | scanned/legacy-font PDF; OCR is not implemented |
| coverage shows async code uncovered | missing `concurrency = ["greenlet","thread"]` |

## 11. Known limitations

See [audit/master_implementation_status.md](audit/master_implementation_status.md) (section "Remaining work") – the authoritative list.
