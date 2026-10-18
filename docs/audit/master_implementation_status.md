# Master implementation status

**Date:** 2026-10-19 · **Branch:** `audit/tn-data-verification` · **Not pushed, not merged**
**Release recommendation: `BLOCKED`** (see §7). The code is reviewable; the platform is *not* production-ready and its data
is *not* officially verified.

Legend — **Tested**: automated tests ran green on real infrastructure (see [final_build_validation.md](final_build_validation.md)).
**Run-only**: executed once manually, no automated test. **Not run**: written but never executed.

## 1. Status by component

### Implemented and tested

| Area | What exists | Evidence |
|---|---|---|
| Database | Baseline schema + 7 migrations + idempotent seed runner, constraint probes, upgrade-path test | `db_verify` OK on real PostGIS and in stub mode; 77 SQL-vs-schema conformance tests |
| Verification governance | status log, `official_verified ⇒ reference` CHECK, safe defaults, demotion of 77 unsupported claims | transition-rule unit tests, DB constraint/log/upgrade-path tests (`test_schemas_and_rules.py`, `test_api_admin_chat_governance.py`) |
| Auth & access | register/login/refresh/logout, Argon2, PyJWT, roles, ownership checks, lockout, rate limits, audit trail | `test_jwt_and_rbac.py`, `test_api_auth_catalog.py`, `test_security.py` (incl. cross-citizen access cases) |
| Catalogue APIs | schemes, services, departments, documents, citizens (+consent), public stats | API tests, E2E |
| Eligibility engine | deterministic rule evaluator (UNKNOWN never guessed) | unit + API tests |
| Complaints | submit/track/list/detail, routing, SLA, state machine, scheduler (idempotent), assignment state | `test_api_complaints.py`, `test_complaint_routing.py`, `test_complaint_rules.py` |
| Spatial | `resolve_jurisdiction`, location trigger, GIST/geography indexes, facilities search | 18 tests on **real PostGIS 3.6.2** (synthetic polygons) |
| Synthetic data | seeded, labelled, isolated, replace-scoped generator | 20 tests |
| Ingestion | allow-listed, robots-aware, hash-deduped, staged, failure-logged | 18 tests (mocked HTTP) + **real run** of 4 PDFs from tn.gov.in |
| Embeddings | local BGE / OpenAI / test providers, strict dimensions, retries, re-embedding | 13 tests + **real BGE run** |
| Retrieval & assistant | hybrid ranking, citations to chunk/page, validated answers, injection defences, abstention | 35 tests + 13-question eval on the real model |
| Knowledge graph | idempotent rebuild, privacy rules, failure safety | 16 tests incl. 6 on **real Neo4j 5.26** |
| Admin | live metrics, complaint backlog + legal moves, department performance, verification queue, audited SQL workspace | API + E2E |
| Frontend | auth, EN/தமிழ் toggle, scheme/service discovery, complaint flow, assistant, admin console, error/empty/loading states | **53 Playwright tests** against the real stack; `tsc`, `next lint`, production build clean |
| Accessibility | automated WCAG 2.1 A/AA scans of 11 views | 12 tests (found and fixed 3 critical defects) |
| Security hygiene | headers, body cap, hidden docs in production, secret guard, dependency audit (0 findings Python and npm), no third-party requests | tests + audits |

### Implemented but not integration-tested / not run

| Item | Gap |
|---|---|
| `docker-compose.yml`, `Makefile` targets, Dockerfiles | no Docker / `make` available; YAML parse-validated only |
| `.github/workflows/ci.yml` | never executed on GitHub Actions |
| OpenAI / Google LLM wrappers (`app/ai/orchestration/llm.py`) | no API keys; only the validation layer is tested with fakes |
| OpenAI embeddings provider | HTTP mocked; no real call |
| Project's own `postgis/postgis:16-3.4` image | tests ran on PostGIS 3.6.2 |

### Partially implemented

| Item | State |
|---|---|
| Evidence upload | authorisation + validation done; storage **not implemented** – returns 503 "NOT saved" |
| Officer / department user interface | no UI; officers can only use the API (admin console is for state/system admins) |
| Tamil support | interface chrome + database `name_ta` fields; many page texts remain English; translations **unreviewed** by a translator |
| Complaint location | manual/“use my location” coordinates only; no map picker |
| Documents library | page exists and lists ingested documents; no upload/ingestion UI |
| Jurisdiction resolution | logic verified on synthetic boxes; **no real boundary polygons loaded** |
| Rate limiting | in-process (per worker) |

### Missing

* Official-source evidence for any record (so zero `official_verified`); eligibility **rules** for every scheme; real authorities, offices and officers; district/taluk/ward boundary data; government facilities data.
* Redis-backed shared limits, token revocation/refresh rotation, e-mail verification, password reset, MFA for administrators.
* OCR (scanned and legacy-font PDFs are recorded but not searchable); GO/circular listing connectors beyond "PDF links on one page".
* Production artefacts: hardened images, TLS/proxy, backups and restore procedure, monitoring, secret manager integration.
* Alembic (SQL files are the source of truth).

### Blocked by unavailable infrastructure

Docker flows; `make`; GitHub Actions run; PostGIS 3.4 image; real LLM; MinIO; Redis.

### Unsupported by sufficient official-source evidence (kept `provisional`)

All 38 districts (incl. every LGD code and the Tiruvannamalai "583" correction), 17 departments, 10 services (including the uniform ₹60 e-Sevai charge, "Free" fees and processing times), 11 schemes (GO numbers are dataset assertions, not confirmed), SLA targets (platform targets, not statutory), and the Breakfast Scheme's department assignment (a search result suggests Social Welfare, unconfirmed). `PM-Kisan` is `externally_referenced` (central scheme).

## 2. Data verification summary

| Class | Count | Notes |
|---|---|---|
| `official_verified` | **0** | no official document located and checked for any record |
| `externally_referenced` | 1 | PM-Kisan (central) |
| `provisional` | 76 | 38 districts, 17 departments, 10 services, 11 schemes |
| `unverified` | ingested documents | origin official, content unchecked |
| synthetic | generated on request only | `is_synthetic` + `@synthetic.invalid`; excluded from metrics and the graph |

Attempts this phase: the CMCHIS site renders its body with JavaScript (only the title was retrievable); the e-Sevai page
states **119 services** and fees "if any" with **no amounts** (so the seeded 10-service subset and its charges are unsupported);
`tn.gov.in/department` returned only a redirect stub; GO numbers could not be located. Records stay provisional until a
reviewer supplies specific official documents. Decision register: [verification_decisions_2026-10-18.csv](verification_decisions_2026-10-18.csv).

## 3. Defects found and fixed during this build (selection)

| Area | Before | After |
|---|---|---|
| Backend SQL | 26 of 65 statements referenced non-existent columns; registration/login could not work | all prepare against the schema; conformance test |
| Authorisation | any signed-in user could read any complaint / conversation; `/admin/health` had no auth; evidence upload no ownership check | ownership + role checks, all tested |
| Logging | every `logger.info` raised | fixed |
| Next.js | 15.0.0 with critical advisories (incl. RCE) | 15.5.28; `npm audit --omit=dev` = 0 |
| JWT library | unmaintained `python-jose` with unfixed advisories | PyJWT, pinned algorithm, mandatory `exp` |
| Frontend ↔ API | complaint form posted fields the API rejected; no login page; admin panels read fields that do not exist; SQL workspace crashed on success | rewritten against the real contract; E2E-tested |
| Honesty | "75M citizens served", "30+ schemes", "verified" badges on everything, "Free" fees | live counts, status badges, "unconfirmed" labels |
| Spatial | boundary points unresolved; overlaps arbitrary; facility search could not use its index | migration 005 + tests |
| Retrieval | irrelevant records crowded out the right document; assistant could never abstain once embeddings existed | unified ranking, similarity floor, semantic veto |
| Privacy | fonts fetched from Google on every page; registrant e-mail logged | self-hosted fonts; no PII in logs/audit |
| Build | `npm install` failed (non-existent package); Docker `npm ci` had no lockfile | fixed, lockfile committed |

## 4. Security posture

**Resolved:** items in §3 plus lockout/rate limits, security headers, body-size cap, SQL-workspace read-only transaction and credential redaction, audit trail, production secret guard, compose without default secrets and with localhost-only data stores.

**Outstanding (honest list):** in-process rate limiting; refresh tokens not revocable and stored in `localStorage` (XSS would expose them; consider httpOnly cookies + CSRF protection); no admin MFA; no password reset/e-mail verification; admin SQL workspace is powerful (system_admin, read-only, audited, but still reads personal data by design); JWT secret rotation procedure absent; no penetration test; Python/Node transitive dependency review limited to `pip-audit`/`npm audit`; CORS origins are configuration-driven and must be set explicitly in production.

## 5. Where to resume (priority order)

1. **Get official evidence** (needs a human with access to the GO PDFs / department pages): verify the 12 schemes, 17 departments, 10 services (incl. fees and timings) and the 38 districts' LGD codes; record `source_document_ref` and promote through reviewed seed changes. Load real eligibility rules from the verified orders.
2. Run the Docker stack, the Makefile targets and the GitHub Actions workflow once; fix what breaks (expect small path/version issues).
3. Load authoritative boundary polygons and facility data; re-run the PostGIS tests on the project's 3.4 image.
4. Load real authorities/offices (from official directories) so complaints route to actual offices; add an officer UI.
5. Implement evidence storage (MinIO) and OCR; widen ingestion beyond single-page link scraping to GO listings.
6. Enlarge the retrieval golden set and re-calibrate `RETRIEVAL_MIN_SIMILARITY`; try a real LLM behind the validation layer.
7. Security follow-ups in §4; production images, TLS, backups, monitoring; Tamil translation review.

## 6. Test counts

428 backend + 53 browser = **481 passed, 0 failed, 0 skipped**; 87% line coverage of 3,509 statements (greenlet-aware);
52 of 52 API routes referenced by tests. Generated detail: [test_inventory.md](test_inventory.md), [route_test_inventory.md](route_test_inventory.md).

## 7. Release recommendation: `BLOCKED`

Not `READY_FOR_REVIEW` for release because essential verification evidence is missing (no record is officially verified), the
container/CI paths have never been executed, and the production-readiness items in §1 and §4 are open. The branch is suitable
for **code review**; it must not be presented to citizens as verified government information, and not be deployed on the basis
of this report.
