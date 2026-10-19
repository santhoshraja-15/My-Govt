# Deployment reproducibility & release-gate audit

## A. Executive decision

**Decision: `BLOCKED`.**

| | |
|---|---|
| Date | 2026-10-19 |
| Environment | Windows 11, Python 3.11.9 (project targets 3.12), Node 25.6.0 (CI uses 22), GNU Make 4.4.1 (WSL2 Ubuntu). **No Docker** (not on Windows, not in WSL; WSL `sudo` needs a password). |
| Branch | `audit/tn-data-verification` (never merged to `main`) |
| HEAD at time of writing | `f046712` (report commit follows) |
| Hosted CI result | **PASS — all 9 jobs green** for `f046712` (run 39224287935: Backend, Playwright, Frontend, Security, SQL provenance, and 4 image-build jobs), previously all 5 original jobs green for `3e42db4` (run 39220815138). Reproduced on GitHub, not locally. Earlier runs failed; causes in D. Counts per job were not retrieved; the workflow itself fails on any skipped test. |

Why blocked, independent of CI: no government record is `official_verified` (0 of 77), the Docker/Compose stack has never been
built or started by anyone, and production security controls remain open (see E).

## B. Release-gate matrix

"Reproduced now" = executed during this audit. "Historical" = executed in an earlier session on local infrastructure.

| Gate | Command | Result | Evidence | Blocker / next action |
|---|---|---|---|---|
| Repo baseline | `git status`, `git log` | PASS (reproduced now) | clean tree, branch above, HEAD `780eb61` | — |
| Compose validation | `docker compose config` | NOT RUN — PREREQUISITE UNAVAILABLE | no Docker | YAML parse-checked only (historical) |
| Application image builds | `images` CI job (docker/build-push-action, `push: false`) for `docker/backend/Dockerfile`, `docker/frontend/Dockerfile`, `docker/backend/Dockerfile.prod`, `docker/frontend/Dockerfile.prod` | **PASS on hosted CI (run 39224287935), all four.** Earlier **defect found and fixed**: invalid `build-backend` (guarded by `test_packaging.py`). Local build NOT RUN (no Docker). | run 39224287935 | Built ≠ verified runtime |
| Image property checks | same job, post-build steps | **PASS on hosted CI**: prod backend non-root, no pytest/ruff, imports fastapi/async SQLAlchemy/greenlet/asyncpg/torch, `app/main.py` present, no `--reload`, HEALTHCHECK defined, no env file; prod frontend non-root, `server.js` + `.next/static` present, HEALTHCHECK, container answers `GET /` without 5xx; dev images import/`next` present | run 39224287935 | The frontend probe has no backend/DB; backend prod image was never started |
| Postgres image build | `docker build docker/postgres` | **PASS on hosted CI (run 39220815138, image built in the Backend and E2E jobs)**. Failed in earlier runs `3ae63b9`, `be07fb5`, `5b5a9c0`, `13b49c8`. Cause (from the build's own annotation): `postgis/postgis:16-3.4` and `16-3.5` are Debian bullseye; `apt.postgresql.org bullseye-pgdg` returns 404 so `postgresql-16-pgvector` cannot install. Fixed by `780eb61` (base `postgres:16-bookworm` + pgdg `postgresql-16-postgis-3`, `-scripts`, `-pgvector`). | annotations of runs 39213304212/39213525821/39213844357 | Fix confirmed on hosted CI. Local image build still NOT RUN (no Docker) |
| Stack startup / health | `make up`, `make health` | NOT RUN — PREREQUISITE UNAVAILABLE | no Docker | — |
| DB init / migrations | `make db-init`, `migrate-sql`, `db_verify` | Historical PASS locally; **hosted PASS** (Backend job runs `db_verify` and schema/SQL conformance on the project image) | `final_build_validation.md`, run 39220815138 | Compose-based `make db-init` still NOT RUN |
| Seed idempotency | `scripts.seed` twice | Historical PASS (tests) | `milestone_2_validation.md` | — |
| Makefile workflows | `make -n <target>` ×35 | **PASS (reproduced now): expansion exit 0 for all targets.** Dry-run only; no target executed. `migrate`/`migrate-down` intentionally print a message and exit 1 when really run. | GNU Make 4.4.1 | Real execution needs Docker |
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
| `f046712` | CI `images` job (4-image matrix, property checks, frontend start-up probe), matrix-coverage test, `pyyaml==6.0.3` in `requirements-ci.txt`, stale workflow header corrected |

Consequence to watch: PostGIS version on the new image is whatever pgdg ships for bookworm (not 3.4); earlier PostGIS tests ran on 3.6.2.

## E. Remaining blockers

* **Critical:** no officially verified government data; do not present as verified.
* **High:** Docker Compose stack and every `docker compose`-based Make target never executed (no Docker). The images build, but the backend production image has never been started, with or without a database; services have never run together in Compose.
* **High:** production security controls (E list above); no TLS, backups, monitoring.
* **Medium:** no real boundary data; evidence upload intentionally returns 503; no officer UI; Python 3.11 locally vs 3.12 target.
* **Low:** Node 20 deprecation notice for `actions/checkout@v4`/`upload-artifact@v4`.

## F. Ordered next steps

1. Retrieve per-job counts (tests passed, Playwright count) for the green run, and compare with the historical 428 + 53.
2. Add a hosted Compose job: bring up postgres + backend (prod image) + frontend, hit `/health`, run `db_verify` through the Makefile paths.
3. Install Docker (Docker Desktop or WSL), then run `docker compose config`, `make up`, `make health`, `make db-verify`, `make test`; record exit codes.
4. Obtain human-validated official evidence for schemes, departments, services, districts; record `source_document_ref`; promote through reviewed seed changes.
5. Load authoritative boundaries; re-run PostGIS tests on the project image.
6. Close the security items in `master_implementation_status.md` §4.

## G. Release decision

`BLOCKED`. Green hosted CI shows the code builds and its tests pass on a PostGIS/pgvector image; it does not show the data is accurate, the Compose stack works, or the system is production-ready.
