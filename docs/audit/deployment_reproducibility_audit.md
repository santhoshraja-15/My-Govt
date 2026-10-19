# Deployment reproducibility & release-gate audit

## A. Executive decision

**Decision: `BLOCKED`.**

| | |
|---|---|
| Date | 2026-10-19 |
| Environment | Windows 11, Python 3.11.9 (project targets 3.12), Node 25.6.0 (CI uses 22), GNU Make 4.4.1 (WSL2 Ubuntu). **No Docker** (not on Windows, not in WSL; WSL `sudo` needs a password). |
| Branch | `audit/tn-data-verification` (never merged to `main`) |
| HEAD at time of writing | `43c3067` (report commit follows) |
| Hosted CI result | **PASS — all 10 jobs green** for `43c3067` (run 39240522682: Backend, Playwright, Frontend, Security, SQL provenance, 4 image builds, Compose stack incl. strict health assertion and the demo overlay checks). Earlier green runs: `3c2a651` (39226963350, before the strict health check and demo steps). Earlier: 9/9 for `f046712` (run 39224287935, before the Compose job existed), 5/5 for `3e42db4`. Reproduced on GitHub, not locally. Earlier runs failed; causes in D. Counts per job were not retrieved; the workflow itself fails on any skipped test. |

Why blocked, independent of CI: no government record is `official_verified` (0 of 77), the Docker/Compose stack has never been
built or started by anyone, and production security controls remain open (see E).

## B. Release-gate matrix

"Reproduced now" = executed during this audit. "Historical" = executed in an earlier session on local infrastructure.

| Gate | Command | Result | Evidence | Blocker / next action |
|---|---|---|---|---|
| Repo baseline | `git status`, `git log` | PASS (reproduced now) | clean tree, branch above, HEAD `780eb61` | — |
| Compose validation | `docker compose config -q` (CI `compose` job, throw-away `.env`) | **PASS on hosted CI (run 39226963350)**. First run of this job FAILED: `minio/minio:latest` no longer exists on Docker Hub ("pull access denied") — fixed by `3c2a651`. Local run NOT RUN (no Docker). | run 39226963350 | — |
| Application image builds | `images` CI job (docker/build-push-action, `push: false`) for `docker/backend/Dockerfile`, `docker/frontend/Dockerfile`, `docker/backend/Dockerfile.prod`, `docker/frontend/Dockerfile.prod` | **PASS on hosted CI (run 39224287935), all four.** Earlier **defect found and fixed**: invalid `build-backend` (guarded by `test_packaging.py`). Local build NOT RUN (no Docker). | run 39224287935 | Built ≠ verified runtime |
| Image property checks | same job, post-build steps | **PASS on hosted CI**: prod backend non-root, no pytest/ruff, imports fastapi/async SQLAlchemy/greenlet/asyncpg/torch, `app/main.py` present, no `--reload`, HEALTHCHECK defined, no env file; prod frontend non-root, `server.js` + `.next/static` present, HEALTHCHECK, container answers `GET /` without 5xx; dev images import/`next` present | run 39224287935 | The frontend probe has no backend/DB; backend prod image was never started |
| Postgres image build | `docker build docker/postgres` | **PASS on hosted CI (run 39220815138, image built in the Backend and E2E jobs)**. Failed in earlier runs `3ae63b9`, `be07fb5`, `5b5a9c0`, `13b49c8`. Cause (from the build's own annotation): `postgis/postgis:16-3.4` and `16-3.5` are Debian bullseye; `apt.postgresql.org bullseye-pgdg` returns 404 so `postgresql-16-pgvector` cannot install. Fixed by `780eb61` (base `postgres:16-bookworm` + pgdg `postgresql-16-postgis-3`, `-scripts`, `-pgvector`). | annotations of runs 39213304212/39213525821/39213844357 | Fix confirmed on hosted CI. Local image build still NOT RUN (no Docker) |
| Strict health + demo overlay | `assert_health.py` (postgresql/neo4j/redis must be healthy; only minio may be unhealthy), then `make demo` and `check_demo.py` (21 live API checks: role logins, department scoping, assignment, state-machine refusal, eligibility, admin overview, verification statuses) | **PASS on hosted CI (run 39240522682)**. The first strict run FAILED and exposed a real backend defect (see D, `0441e60`). | run 39240522682 | Demo checks run against the dev images, not the production images |
| Stack startup / health | `docker compose up -d --build` (postgres, neo4j, redis, backend, worker, frontend; minio now opt-in), wait for backend Docker health, then `curl /health`, `/api/v1/public/stats`, frontend `GET /` | **PASS on hosted CI (run 39226963350)**. Not covered: `make up`/`make health` themselves (the job calls compose/curl directly), worker behaviour, MinIO (not started), `/health` field values (only HTTP success), prod images inside Compose | run 39226963350 | Run services together with production images; assert `/health` services |
| DB init / migrations | `make db-init`, `migrate-sql`, `db_verify` | Historical PASS locally; **hosted PASS** twice: Backend job (`db_verify`, schema/SQL conformance on the project image) and Compose job (`make db-init` = schema + all migrations + seed, then `make db-verify`) | `final_build_validation.md`, runs 39220815138, 39226963350 | — |
| Seed idempotency | `scripts.seed` twice | Historical PASS (tests) + hosted: `make db-init` seeds once and `make seed-verify` re-checks integrity/provenance in the real stack (a second *seed* run inside Compose was not executed) | `milestone_2_validation.md`, run 39226963350 | — |
| Makefile workflows | `make -n <target>` ×35 | **PASS (reproduced now): expansion exit 0 for all targets.** Dry-run only; no target executed. `migrate`/`migrate-down` intentionally print a message and exit 1 when really run. | GNU Make 4.4.1 | Executed on hosted CI (run 39226963350): `db-init` (→ `schema`, `migrate-sql`, `seed`), `db-verify`, `seed-verify` — PASS. Not executed anywhere: `up`, `down`, `build`, `test*`, `lint`, `embed`, `ingest`, `graph-rebuild`, `scheduler`, `eval`, `e2e`, `synth-db`, `seed-synthetic`, `shell-*`, `clean`, `health` |
| Backend tests | `pytest` | Historical PASS: 428 passed, 0 skipped, 87% coverage. **Hosted PASS** (job success, includes PostGIS and Neo4j service tests; skipped tests fail the job) | `final_build_validation.md` | Infra currently stopped; hosted result pending |
| Frontend checks/build | `tsc`, `next lint`, `next build` | **PASS on hosted CI** (3 consecutive runs) + historical local | CI jobs | — |
| Playwright | `npx playwright test` | Historical PASS: 53/53 incl. axe. **Hosted PASS** | run 39220815138 | — |
| GitHub Actions | `.github/workflows/ci.yml` | Latest run: Security, SQL provenance, Frontend, Backend, E2E all PASS. Earlier runs failed (see D). | Actions API, run 39220815138 | — |
| Dependency audits | pip-audit, npm audit, gitleaks | PASS on hosted CI (Security job; `pip-audit` on the pinned CI requirements) + historical 0 findings | CI | — |
| Auth / complaint workflows | API + E2E tests | Historical PASS | tests | not re-run now |
| Retrieval / AI | 13-question eval, real BGE model | Historical PASS; no real LLM | — | no API keys |
| Official data verification | — | **FAIL / unresolved**: official_verified 0; externally_referenced 1 (PM-Kisan); provisional 76; documents `unverified`; ₹60/"Free" fees unconfirmed | `master_implementation_status.md`, decisions CSV | needs human-validated authoritative evidence |
| Real geospatial data | — | NOT RUN — no boundary polygons loaded (synthetic only) | — | load authoritative boundaries |
| Production security controls | — | OPEN: in-process rate limits, refresh tokens in `localStorage`, no admin MFA/reset flow, no TLS/backups/monitoring | `master_implementation_status.md` §4 | — |

## C. Reproduction evidence

Reproduced now:

* `git status --short` → empty; `git log --oneline -6` → `780eb61 … 1c3e9fb`; branch `audit/tn-data-verification`.
* `make -n <target>` for 35 targets in WSL (GNU Make 4.4.1), all exit 0; Makefile contains 0 CR characters.
* `pytest tests/unit/test_packaging.py` → 4 passed (exit 0); `ruff check` → clean.
* `which docker` (Git Bash and WSL) → not found. Local image build **NOT RUN**.
* Hosted CI failure text, verbatim essence: `E: The repository 'http://apt.postgresql.org/pub/repos/apt bullseye-pgdg Release' does not have a Release file` → `docker build` exit 1.

Historical (earlier session, local infra, not repeated): backend 428 passed / 0 failed / 0 skipped, 87% coverage; Playwright 53 passed; db_verify OK.

A successful local build, if one is later possible, would not prove the hosted run passed, and vice versa.

## D. Changes made (all on this branch)

| Commit | Change |
|---|---|
| `3ae63b9` | `backend/pyproject.toml` build-backend → `setuptools.build_meta`; `.dockerignore` files; `test_packaging.py` |
| `be07fb5` | CI: `POSTGRES_DB=mygovt` for the container, readiness loop fails with container logs (this was a hypothesis, **not** the root cause); test that CI containers set it |
| `5b5a9c0` | CI: publish the image-build failure as an annotation (diagnosis aid) |
| `13b49c8` | Dockerfile base `postgis/postgis:16-3.5` — **wrong**: still bullseye (superseded) |
| `780eb61` | Dockerfile base `postgres:16-bookworm` + pgdg PostGIS/pgvector packages — confirmed on hosted CI |

| `5a9fd9e` | CI: `.github/scripts/annotate_failure.py` publishes failed-step summaries as annotations |
| `6a29e90` | `greenlet==3.5.6` added to `requirements-ci.txt` — its absence broke the backend tests (coverage `concurrency=greenlet`) and the E2E API server (SQLAlchemy asyncio). Reproduced in a clean venv built from the file; production already gets it via `sqlalchemy[asyncio]` |
| `e088b9e` | `setuptools` added to `requirements-ci.txt` — `test_packaging.py` imports the build backend and py3.12 venvs lack setuptools (hosted: 434 passed, 1 failed before this) |
| `3e42db4` | `setuptools` pinned to 83.0.0 — 80.9.0 failed `pip-audit` (PYSEC-2026-3447), reproduced locally |
| `a824e5c`, `7a2f468` | Production images `docker/backend/Dockerfile.prod`, `docker/frontend/Dockerfile.prod` + static tests; LF endings for `Dockerfile.*`. Built on hosted CI by `f046712` |
| `7e6c659`, `3c2a651` | CI `compose` job + `.github/scripts/make_ci_env.py` (throw-away `.env`); first run failed because `minio/minio` no longer exists on Docker Hub → MinIO moved to opt-in profile `storage` using `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z` (**pull-unverified**, never started in CI) + test |
| `0441e60` | **Backend defect found by the strict health check:** `check_minio` ran the blocking MinIO SDK on the event loop; with MinIO absent its retries stalled the loop and the Redis check reported "Timeout connecting to server" although a manual ping succeeded. MinIO probe now runs in a worker thread with short timeouts, Redis has explicit timeouts, every check is bounded; regression test fails on the old code. Also: `prefers-reduced-motion` CSS so axe scans do not depend on animation timing (the `/assistant` contrast scan was flaky on the hosted runner) |
| `43c3067` | health isolation test fakes `urllib3` (not in the CI requirements) |
| `6f1f2cb` … `4115cc5` | Frontend: Tailwind had **never been compiled** (no `postcss.config.js`) so every page shipped unstyled; added, component classes moved into `@layer components`, WCAG contrast fixed, dead footer links and misleading "official/verified" copy removed; citizen dashboard, officer console, department scoping, demo environment (see `docs/demo.md`) |
| `f046712` | CI `images` job (4-image matrix, property checks, frontend start-up probe), matrix-coverage test, `pyyaml==6.0.3` in `requirements-ci.txt`, stale workflow header corrected |

Consequence to watch: PostGIS version on the new image is whatever pgdg ships for bookworm (not 3.4); earlier PostGIS tests ran on 3.6.2.

## E. Remaining blockers

* **Critical:** no officially verified government data; do not present as verified.
* **High:** The backend production image has never been started (neither alone nor in Compose); the Compose job uses the dev images (reload, source mounts). Most Make targets (see matrix) never executed. MinIO has no working verified image reference.
* **Medium:** worker behaviour, Neo4j graph rebuild and embeddings paths are untested in Compose (health states of postgresql/neo4j/redis are now asserted).
* **High:** production security controls (E list above); no TLS, backups, monitoring.
* **Medium:** no real boundary data; evidence upload intentionally returns 503; no officer UI; Python 3.11 locally vs 3.12 target.
* **Low:** Node 20 deprecation notice for `actions/checkout@v4`/`upload-artifact@v4`.

## F. Ordered next steps

1. Retrieve per-job counts (tests passed, Playwright count) for the green run, and compare with the historical 428 + 53.
2. Run the backend production image against the Compose database and execute `make test-unit`/`lint`/`graph-rebuild` in the Compose job.
3. Decide the object-storage image (verified MinIO source or another S3 store) before implementing evidence storage.
4. Obtain human-validated official evidence for schemes, departments, services, districts; record `source_document_ref`; promote through reviewed seed changes.
5. Load authoritative boundaries; re-run PostGIS tests on the project image.
6. Close the security items in `master_implementation_status.md` §4.
7. (Optional) run the stack locally with Docker for faster iteration; hosted CI already executes it.

## G. Release decision

`BLOCKED`. Green hosted CI shows the code builds, its tests pass on a PostGIS/pgvector image, the four images build and the dev Compose stack starts and initialises its database; it does not show the data is accurate, the Compose stack works, or the system is production-ready.
