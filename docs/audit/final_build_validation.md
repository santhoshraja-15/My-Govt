# Final build validation

**Date:** 2026-10-19 · **Branch:** `audit/tn-data-verification` · **HEAD at time of the runs:** `026eac4` (plus documentation commits)
**Nothing was pushed or merged.**

This is a record of commands that were actually executed and what they printed. Where something could not be run it
says so; nothing here is inferred.

## 1. Environment actually used

| Component | Version / detail |
|---|---|
| OS | Windows 11 Home (10.0.26200) |
| Python | 3.11.9 (the project targets 3.12; CI is configured for 3.12 but has not run) |
| Node / npm | 25.6.0 / 11.8.0 (CI is configured for Node 22 but has not run) |
| PostgreSQL | 16.15 (conda-forge, disposable instance, port 54329) |
| PostGIS | 3.6.2 — OSGeo Windows bundle (md5 verified), GEOS 3.14.1, PROJ 8.2.1. **Not** the project's `postgis/postgis:16-3.4` image |
| pgvector | conda-forge build |
| Neo4j | Community 5.26.0 on JDK 21.0.12 (local, disposable) |
| Embedding model | `BAAI/bge-large-en-v1.5` (1024-d) via sentence-transformers 6.1.0 / torch 2.14.1 (CPU) |
| Frontend | Next.js 15.5.28, React 18.3.1, Playwright 1.64.1 (Chromium headless shell) |
| **Not available** | Docker, `make`, `psql` on PATH, GitHub Actions runner, any LLM API key, MinIO, Redis |

## 2. Results

### Backend (`backend/`, all infrastructure present)

```
$ TEST_ADMIN_DSN=… TEST_POSTGIS=1 TEST_NEO4J_URI=… pytest tests -q -rs --cov --junitxml=pytest-report.xml
428 passed in 110.81s          exit 0      (0 failed, 0 skipped)      coverage: 3509 statements, 449 missed = 87%
$ ruff check app scripts etl knowledge_graph ai tests
All checks passed!             exit 0
$ mypy app scripts etl knowledge_graph ai
Success: no issues found in 89 source files           exit 0
$ python -m scripts.db_verify --admin-dsn …            (real PostGIS)
result: OK (0 failing step(s))                         exit 0
$ python -m scripts.db_verify --admin-dsn … --no-postgis   (stub mode, relational only)
result: OK (0 failing step(s))                         exit 0
$ pip-audit -r requirements-ci.txt
No known vulnerabilities found                         exit 0
```

### Frontend (`frontend/`)

```
$ node_modules/.bin/tsc --noEmit                       exit 0
$ npx next lint                                        ✔ No ESLint warnings or errors   exit 0
$ npm audit --omit=dev                                 found 0 vulnerabilities           exit 0
$ npm run build                                        ✓ Compiled successfully           exit 0
$ npx playwright test                                  (real FastAPI + PostgreSQL + production Next build + Chromium)
53 passed (1.0m)                                       exit 0
```

### AI evaluation (real model, 13 golden questions, `ai/eval/golden_cases.json`)

| Mode | Answerable hit-rate | Top-1 | Correct abstention |
|---|---|---|---|
| Keyword only | 0.8 | 0.8 | 1.0 |
| Hybrid, BAAI/bge-large-en-v1.5 | **1.0** | **0.9** | 1.0 |

13 questions is a *small* set (10 answerable, 3 not). It shows the direction, not a reliable accuracy figure.
`RETRIEVAL_MIN_SIMILARITY = 0.5` is provisionally calibrated on a handful of samples (relevant 0.59–0.85,
irrelevant 0.31–0.40) and must be re-measured with a larger set.

### Real-world runs (not part of the automated suite)

| Run | Result |
|---|---|
| `python -m etl.pipeline --source TN_GOV_PORTAL --page https://www.tn.gov.in/ --limit 4` | 4 official PDFs downloaded, hashed, extracted, chunked, stored (`unverified`); all stages logged. They are **forms**, not government orders – the portal home page links no GOs |
| Same, quality check | The Tamil anthem PDF uses a legacy font; its "text" was `! ! !` and was initially stored as `ok`. A readability check now flags it `empty` (no OCR) |
| `python -m app.ai.embeddings.run --all --provider local` | 1 chunk (the E2E fixture document; 9 chunks in an earlier run on the ingested PDFs) + 12 schemes + 10 services embedded, 0 failures |
| `python -m knowledge_graph.rebuild` (real Neo4j) | 17 Department, 12 Scheme, 10 Service, 17 Authority, 10 Category, 5 Complaint, 1 Document nodes; second run identical; **0** `ELIGIBLE_FOR` edges because no eligibility rules exist |

## 3. What the real runs found that mocks had missed

* Retrieval ranking: generic words ("Tamil Nadu") matched many schemes and pushed the relevant official document out of the citations.
* Vector search always returns neighbours, so without a similarity floor the assistant could never abstain.
* Legacy-font PDFs produce garbage text that looked successful.
* Real PostGIS: boundary points resolved to nothing; overlapping polygons gave arbitrary answers; the facility query could not use its index (fixed in migration 005).
* `structlog` configuration crashed every `logger.info` call; `package.json` referenced a non-existent package; `npm ci` had no lockfile.

## 4. Not executed

| Item | Why |
|---|---|
| `docker compose up`, `make …` targets | no Docker / `make` on the machine; compose YAML parse-validated only |
| GitHub Actions workflow | not run; statically validated (YAML parse); the static provenance job's script was run locally |
| Project's PostGIS 3.4 image | not available; 3.6.2 used |
| Real LLM calls (OpenAI/Google wrappers) | no keys; only the validation layer and fakes are tested |
| OpenAI embeddings | HTTP mocked only |
| Evidence upload to MinIO | not implemented (endpoint refuses with 503) |
| Load, concurrency, penetration testing, manual accessibility review | not performed |
