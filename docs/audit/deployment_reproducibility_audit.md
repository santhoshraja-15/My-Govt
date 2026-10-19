# Deployment reproducibility & release-gate audit

## A. Executive decision

**Decision: `BLOCKED`.**

| | |
|---|---|
| Date | 2026-10-19 |
| Environment | Windows 11, Python 3.11.9 (project targets 3.12), Node 25.6.0 (CI uses 22), GNU Make 4.4.1 (WSL2 Ubuntu). **No Docker** (not on Windows, not in WSL; WSL `sudo` needs a password). |
| Branch | `audit/tn-data-verification` (never merged to `main`) |
| HEAD at time of writing | `780eb61` |
| Hosted CI result for `780eb61` | **UNVERIFIED** — GitHub API rate limit exhausted (resets ≈ 30 min after the last check); a single status check is scheduled. The Postgres image fix is **unconfirmed**. |

Why blocked, independent of CI: no government record is `official_verified` (0 of 77), the Docker/Compose stack has never been
built or started by anyone, and production security controls remain open (see E).

## B. Release-gate matrix

"Reproduced now" = executed during this audit. "Historical" = executed in an earlier session on local infrastructure.

| Gate | Command | Result | Evidence | Blocker / next action |
|---|---|---|---|---|
| Repo baseline | `git status`, `git log` | PASS (reproduced now) | clean tree, branch above, HEAD `780eb61` | — |
| Compose validation | `docker compose config` | NOT RUN — PREREQUISITE UNAVAILABLE | no Docker | YAML parse-checked only (historical) |
| Backend image build | `docker build docker/backend` | NOT RUN locally. **Defect found and fixed**: invalid `build-backend` (historical repro via `pip install -e .`, now guarded by `test_packaging.py`, 4 pass now) | hosted CI does not build this image | Build once with Docker |
| Postgres image build | `docker build docker/postgres` | **FAILED on hosted CI in runs `3ae63b9`, `be07fb5`, `5b5a9c0`, `13b49c8`** (reproduced on GitHub, not locally). Cause (from the build's own annotation): `postgis/postgis:16-3.4` and `16-3.5` are Debian bullseye; `apt.postgresql.org bullseye-pgdg` returns 404 so `postgresql-16-pgvector` cannot install. Fix `780eb61` (base `postgres:16-bookworm` + pgdg `postgresql-16-postgis-3`, `-scripts`, `-pgvector`). | annotations of runs 39213304212/39213525821/39213844357 | **Fix unverified** — result of run for `780eb61` pending |
| Stack startup / health | `make up`, `make health` | NOT RUN — PREREQUISITE UNAVAILABLE | no Docker | — |
| DB init / migrations | `make db-init`, `migrate-sql`, `db_verify` | Historical PASS on local PG16/PostGIS 3.6.2 (not the project image) | `final_build_validation.md` | Re-run on the project image (hosted CI will, once it builds) |
| Seed idempotency | `scripts.seed` twice | Historical PASS (tests) | `milestone_2_validation.md` | — |
| Makefile workflows | `make -n <target>` ×35 | **PASS (reproduced now): expansion exit 0 for all targets.** Dry-run only; no target executed. `migrate`/`migrate-down` intentionally print a message and exit 1 when really run. | GNU Make 4.4.1 | Real execution needs Docker |
| Backend tests | `pytest` | Historical PASS: 428 passed, 0 skipped, 87% coverage. Hosted: unverified | `final_build_validation.md` | Infra currently stopped; hosted result pending |
| Frontend checks/build | `tsc`, `next lint`, `next build` | **PASS on hosted CI** (3 consecutive runs) + historical local | CI jobs | — |
| Playwright | `npx playwright test` | Historical PASS: 53/53 incl. axe. Hosted: blocked at Postgres step in all runs | — | pending image fix |
| GitHub Actions | `.github/workflows/ci.yml` | Ran 4 times: jobs Security, SQL provenance, Frontend PASS; Backend and E2E FAIL at the Postgres image step. Run for `780eb61`: unknown. | Actions API | check after rate-limit reset |
| Dependency audits | pip-audit, npm audit, gitleaks | PASS on hosted CI (Security job) + historical 0 findings | CI | — |
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
| `780eb61` | Dockerfile base `postgres:16-bookworm` + pgdg PostGIS/pgvector packages — unverified |

Consequence to watch: PostGIS version on the new image is whatever pgdg ships for bookworm (not 3.4); earlier PostGIS tests ran on 3.6.2.

## E. Remaining blockers

* **Critical:** no officially verified government data; do not present as verified.
* **High:** Postgres image build fix unverified; Docker Compose stack, backend image and every `docker compose`-based Make target never executed.
* **High:** production security controls (E list above); no TLS, backups, monitoring.
* **Medium:** no real boundary data; evidence upload intentionally returns 503; no officer UI; Python 3.11 locally vs 3.12 target.
* **Low:** Node 20 deprecation notice for `actions/checkout@v4`/`upload-artifact@v4`.

## F. Ordered next steps

1. After the rate limit resets, read the hosted result for `780eb61`; if the image build still fails, read the new annotation and fix the demonstrated cause.
2. If it passes, confirm Backend and E2E jobs completed (pytest 0 skipped, Playwright) and compare with the historical numbers.
3. Install Docker (Docker Desktop or WSL), then run `docker compose config`, `make up`, `make health`, `make db-verify`, `make test`; record exit codes.
4. Obtain human-validated official evidence for schemes, departments, services, districts; record `source_document_ref`; promote through reviewed seed changes.
5. Load authoritative boundaries; re-run PostGIS tests on the project image.
6. Close the security items in `master_implementation_status.md` §4.

## G. Release decision

`BLOCKED`. Removing the Postgres-image blocker alone would not change this.
