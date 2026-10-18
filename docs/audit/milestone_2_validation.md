# Milestone 2 — Backend Reliability, Verification Governance and Tests

**Branch:** `audit/tn-data-verification` (not pushed, not merged)
**Review date:** 2026-10-18
**Status: PARTIALLY COMPLETE.** Backend reliability, verification governance and the automated
test suite are done and verified against a real PostgreSQL 16 + pgvector server. Two items are
**BLOCKED** by the environment and are explicitly *not* claimed as passing: all PostGIS spatial
behaviour, and official-source evidence for any record's `official_verified` status.

---

## 1. Environment actually used

| Item | Value |
|---|---|
| OS / Python | Windows 11, Python 3.11.9 (project targets 3.12; no 3.12-only syntax is used) |
| PostgreSQL | 16.15 + pgvector, from conda-forge, **disposable** instance on port 54329 (`mygovt_test_*` databases only) |
| PostGIS | **Not available** (no Windows build on conda-forge; no Docker). Schema loaded with spatial objects stubbed — see §6 |
| Docker / psql | Not installed on the host |
| Node | `npm install` + `tsc` ran; Playwright / `next lint` did not (see §5) |

Nothing in this milestone touches a database named `mygovt`: the fixtures create and drop
`mygovt_test_<random>` and refuse to run without `TEST_ADMIN_DSN`.

---

## 2. Changes made

### 2.1 Backend ↔ schema alignment (the main reliability fix)
A new harness, `backend/tests/integration/test_sql_schema_conformance.py`, `PREPARE`s every static
SQL statement in `app/` against the real schema. **26 of 65 statements failed on first run**
(the previous audit reported the backend "Complete & Fixed"; it was not). All now pass, and the
dynamic (f-string) statements are exercised by the API tests.

| Area | Defect | Fix |
|---|---|---|
| Auth | `citizen.full_name`, `app_user.citizen_id`, `last_login_at` do not exist (registration/login could never succeed) | Use `citizen.name` / `citizen.user_id`; track `failed_logins` |
| Auth | `/auth/me` response needs `full_name`, dependency did not supply it | Added to the user context |
| Complaints | `reference_number`, `cc.name`, UUID ids, `address`, `ai_*` columns, `is_active` on `sla_rule` — none exist | Rewrote `ComplaintService` against the schema (aliases keep the API contract) |
| Complaints | **IDOR:** any logged-in user could read any complaint | `can_view_complaint` (owner or staff) |
| Complaints | Duplicate history rows (service + `trg_complaint_history`) | Trigger owns history; service annotates remarks / `changed_by` |
| Complaints | Supplied `district_id` overwritten with NULL when jurisdiction lookup returned nothing; failed lookup aborted the transaction | Keep caller value; lookup in a savepoint |
| Complaints | Routing/SLA read non-existent tables/columns | Real `routing_rule` → department → district/state authority; `sla_rule` by category+priority; default hours fallback |
| Scheduler | Escalated from any status (violating the state machine); duplicate history; no escalation record | Only legal source states; trigger history annotated; `complaints.escalation` row to parent authority |
| Schemes / services | `s.name`, `description`, `official_source_url`, `status` on rules, `processing_days` … do not exist | Real columns; `verification_status` + `source_document_ref` now exposed |
| Eligibility | Group with no evaluated mandatory rule counted as PASS; `=` case-sensitive | UNKNOWN; case-insensitive; rule evaluator extracted as a pure function |
| Documents | `doc_type`, `extracted_text`, `summary`, `verified_at` do not exist | `document_type`, `full_text` |
| Citizens | Profile columns and `profile_consent` do not exist | Migration 003 + consent via `identity.consent`; consent revocation deletes the profile |
| GIS | Fallback returned HTTP 200 "unknown" on any DB error; facilities queried a non-existent table | Errors propagate; real `services.government_facility` |
| Chat | 7 mismatches; described provisional data as "verified"; conversations/lineage readable by anyone | Verification-aware citations/trust/wording; ownership checks; per-source `ai.decision_lineage` |
| Admin | Table sample interpolated an unvalidated identifier and returned `password_hash`; SQL workspace allowed `SELECT nextval(...)` | Identifier validation, credential redaction, `SELECT`-only + `READ ONLY` transaction |
| Logging | `structlog.stdlib` processors with a `PrintLogger` → **every `logger.info/warning` raised `AttributeError`** | Fixed processors |
| Config | Placeholder secrets accepted in production | `APP_ENV=production` rejects them |
| Frontend build | `package.json` required non-existent `@radix-ui/react-badge`; Dockerfile uses `npm ci` with no lockfile | Removed dep; committed generated `package-lock.json` |

New migrations: **003** (`complaint.address`, citizen-profile attributes) and **004**
(verification governance, §3). `seed.py`, `db_verify.py`, the Makefile and the test fixtures apply
every `database/migrations/NNN_*.sql` in order.

### 2.2 Honest user-facing wording
`frontend` previously showed a "Verified" badge whenever `verified_at` was set (the seed set it to
`now()` for every row). Replaced by `VerificationBadge`, driven only by `verification_status`, on
scheme list/detail, services and assistant citations. Landing-page copy that claimed "every answer
is grounded in official sources / verified regularly" was reworded.

---

## 3. Verification-status changes and evidence

### 3.1 Evidence review
Task: verify, record by record, the 17 departments, 10 services and 38 districts marked
`official_verified` without document references, and verify the 12 schemes' GO numbers against
actual orders.

What was attempted (2026-10-18):
* Web search for the GO behind **CM Breakfast Scheme** — no order text or number found; one result
  names Social Welfare (not School Education, as seeded) as nodal department.
* Web search for the GO behind **Kalaignar Magalir Urimai Thogai** — guidelines reported in news,
  no order number found.
* Fetch of the official `tn.gov.in/department` listing — returned only a redirect stub.
* The remaining GO references (`GO Ms No 1 Social Welfare 2023`, `GO Ms No 49 Health 2012`, …)
  were not searched individually; the first two attempts showed the official order texts are not
  retrievable through the available tools.

**Result: no official document was located for any record**, so none can retain
`official_verified`. A checksum or a reachable domain is not evidence for a record and was not
used as one.

### 3.2 Decisions (full register: [`verification_decisions_2026-10-18.csv`](verification_decisions_2026-10-18.csv), 77 rows)

| Table | Records | Previous | New | Notes |
|---|---:|---|---|---|
| `administration.district` | 38 | official_verified | **provisional** | LGD codes (incl. Tiruvannamalai = 583) come from the curated JSON; not re-checked against the LGD directory |
| `administration.department` | 17 | official_verified | **provisional** | `verified_at` / `verified_by` cleared |
| `services.service` | 10 | official_verified | **provisional** | `verified_at` / `verified_by` cleared |
| `schemes.scheme` | 11 | official_verified | **provisional** | Dataset-asserted GO/guideline text kept in `source_document_ref` **for follow-up only** (not confirmed); `verified_at` / `verified_by` cleared |
| `schemes.scheme` | 1 (TN-PM-KISAN) | externally_referenced | externally_referenced | unchanged |
| `system.dataset_registry` | 3 | validation_status `official_verified` | **provisional** | checksums prove file integrity only |

Record IDs and relationships are untouched; only status/verification columns change.

### 3.3 Mechanism (migration 004 + seed section 11)
* `system.verification_status_log` records table, record key, old status, new status, **reason**,
  actor and timestamp, written by a trigger on every status change. The seed supplies the reason.
* CHECK `chk_<table>_verified_has_source`: `official_verified` requires a non-blank
  `source_document_ref` (district, department, scheme, service, complaint_category). Added
  `NOT VALID`, then validated by the seed after demotion, so existing databases can upgrade.
* `deprecated` is terminal (trigger).
* District/department column defaults changed from `official_verified` to `provisional` (a latent
  bug in migration 002: any new row silently claimed verification).
* `app/services/verification.py` mirrors the rules for application code.
* **Known limitation:** the CHECK only proves a reference *exists*, not that it was *checked*. A
  scheme that carries the dataset-asserted reference could be flipped to `official_verified` by an
  UPDATE. Promotion should go through a reviewed change to seed section 11 until a promotion
  workflow (reviewer, evidence URL, date) exists.

### 3.4 API / UI filtering behaviour
No endpoint ever filtered on verification status, so directory functionality is unchanged: every
record is still listed. `GET /schemes` and `GET /services` gained an optional
`verification_status` filter; all responses carry `verification_status` and `source_document_ref`.
The UI labels non-verified records instead of hiding them. The chat assistant states when cited
sources are unconfirmed and weights trust by status (provisional ≤ 0.5).

---

## 4. Tests executed — exact commands and outcomes

All run from `backend/` with `PYTHONIOENCODING=utf-8`.

| Command | Result | Exit |
|---|---|---|
| `TEST_ADMIN_DSN=postgresql://postgres@localhost:54329/postgres python -m pytest tests -q -rs` | **248 passed, 5 skipped** in 23.8 s | 0 |
| `python -m pytest tests -q` (no DB configured) | 105 passed, 148 skipped (DB tests skip, never target a default DB) | 0 |
| `python -m scripts.db_verify --admin-dsn … --no-postgis` | `result: OK (0 failing step(s))` — migrations 002–004 apply twice, seed twice is idempotent, 5 negative probes rejected | 0 |
| `mypy app` | `Success: no issues found in 58 source files` (was 13 errors) | 0 |
| `ruff check app scripts tests --select F,E9` | clean | 0 |
| `ruff check app scripts tests` | **532 findings, all pre-existing style debt** (267 E501 line length, 184 UP045 `Optional[...]` style, 21 I001, 19 UP006, …) | 1 |
| `frontend: npm install` then `tsc --noEmit` | installed 488 packages; no type errors | 0 |

Coverage by requested area (all in `backend/tests/`):

| Requested area | Where |
|---|---|
| JWT validity, expiry, RBAC | `unit/test_jwt_and_rbac.py` (expired, tampered, wrong secret, `alg:none`, refresh-as-access, 401/403 paths); `integration/test_api_auth_catalog.py` |
| GIS district/taluk queries & schema compatibility | `integration/test_api_auth_catalog.py::test_gis_districts_and_taluks_match_schema`; conformance harness |
| Complaint validation, routing, transitions | `unit/test_schemas_and_rules.py`, `unit/test_complaint_rules.py` (statuses cross-checked against the DB CHECK), `integration/test_api_complaints.py` |
| SLA deadlines & escalation thresholds | `unit/test_complaint_rules.py`; `integration/test_api_complaints.py` (rule hours, default fallback, scheduler incl. idempotence and parent-authority record) |
| Pydantic schemas | `unit/test_schemas_and_rules.py` (enums cross-checked against DB CHECKs) |
| Scheme & service retrieval | `integration/test_api_auth_catalog.py` (lists, filters, detail, eligibility engine with and without rules) |
| Admin authorization & audit log | `integration/test_api_admin_chat_governance.py` (anonymous/citizen/officer denied, audit columns, append-only trigger, redaction, read-only SQL workspace) |
| Verification transitions & provenance | `unit/test_schemas_and_rules.py::test_validate_transition`; DB-level tests + **upgrade-path test** (legacy `official_verified` rows demoted and logged) |

Limits of these tests: the ST_* statements and the PostGIS-dependent endpoints are not covered
(§6); the chat LLM path is not covered (no provider configured; only the deterministic template);
there are no load or concurrency tests; coverage % was not measured.

---

## 5. Not executed

| Item | Why |
|---|---|
| Playwright / E2E | Milestone 6 |
| `next lint` | No ESLint config in the repo (`next lint` would prompt interactively); needs a config — Milestone 7 |
| `docker compose` flows (`make db-init`, `make db-verify`, `make test`) | Docker unavailable; Makefile targets updated but **not run** |
| Frontend rendering of the new badges | Type-checked only, not viewed in a browser |

---

## 6. PostGIS — BLOCKED (not claimed)

`tests/integration/test_postgis_spatial.py` contains real assertions for:
* `administration.resolve_jurisdiction` (inside / outside a polygon),
* the `trg_complaint_location` trigger (geometry + jurisdiction fill),
* creation of all seven GIST indexes (`idx_*_geom`),
* `GET /gis/resolve-jurisdiction` and `GET /gis/facilities` (distance ordering, radius filter).

They are skipped with reason *BLOCKED: needs real PostGIS* and have **never been executed**. With
the stub (geometry → `text`, three `ST_*` functions returning NULL/false) the relational schema,
the complaint flow and `resolve_jurisdiction`'s *non-spatial* behaviour are exercised, but
nothing spatial is verified. To close: run against `postgis/postgis:16-3.4` with
`TEST_ADMIN_DSN=… TEST_POSTGIS=1 pytest -m postgis` and record the output here.

---

## 7. Remaining defects and limitations

1. **No record is `official_verified`.** Re-verification needs access to the official GO texts /
   department pages (or a human reviewer) and a promotion workflow (§3.3).
2. LGD codes in the district master were not checked against the LGD directory; the "583" fix in
   the previous audit is unverified.
3. `complaints.routing_rule` and `administration.authority` are **not seeded**, so routing yields a
   department (from `default_department_id`) but no authority in a fresh database. The seed header
   "Deterministic Routing" is aspirational. Needs real authority data.
4. The seeded Breakfast Scheme is attached to School Education; a search result suggests Social
   Welfare is the nodal department — unconfirmed, flagged for the reviewer.
5. Services have no `service_requirement`/`processing_time` data in the seed; the UI shows less than the contract allows.
6. Backend still has 532 style findings (mostly line length / `Optional` syntax) and `ruff` config
   was migrated to `[tool.ruff.lint]` because ruff 0.17 ignores the old keys.
7. `admin` role list includes `data_steward`, which the `app_user.role` CHECK does not allow (dead role).
8. Refresh tokens are not revocable (logout is a no-op); no login lockout beyond counting `failed_logins`.
9. Evidence upload endpoint is still a stub (MinIO not wired).
10. `next@15.0.0` is flagged deprecated for a security advisory; no ESLint config; Playwright suite absent.
11. Docker-based paths (`make db-init`, `make db-verify`, compose builds) remain unexecuted.
12. Python 3.12 (project target) was not used; Python 3.11 only.
