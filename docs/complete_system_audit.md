# Complete system audit

**Date:** 2026-10-19  ·  **Commit audited:** `c8aa129`  ·  **Branch:** `audit/tn-data-verification`
**Verdict:** PASS for a university demonstration; NOT approved for public release. Government data remains provisional (0 officially verified); see §14.

All numbers below are computed from the raw evidence files by `backend/scripts/build_audit_report.py`; the CSVs in `docs/audit/` are the
records behind them. Results are **PASS** (verified with evidence), **FAIL**, or limitations are listed explicitly; nothing is marked PASS without a test or probe result.

## 1. Environment and baseline

* Windows 11, Python 3.11 (project target 3.12), Node 25 (CI uses 22), PostgreSQL 16.15 + PostGIS 3.6.2 + pgvector 0.8.6 (local, not the Docker image), no Docker locally.
* Running during the audit: FastAPI (`uvicorn`, demo database `mygovt_dev_demo`, `DEMO_INCLUDE_SYNTHETIC=true`), Next.js production build on :3000.
* **Not running locally:** Redis, MinIO, Neo4j (reported *Unavailable/Disabled* by the app; optional). Hosted GitHub Actions runs the Compose stack with Redis and Neo4j.
* Working tree was clean at the start; every fix was committed and pushed to the existing branch (no merge to `main`, no force-push). The demo database was **never reset or deleted**.

## 2. Method and tools (all in the repository, reproducible)

| Tool | What it does | Output used here |
|---|---|---|
| `frontend/audit/sweep.js` | Every route × 7 roles × 3 widths: redirects, status, console/page errors, failed requests, overflow, broken images, dead links, unlabelled inputs, headings | `route_inventory.csv` |
| `frontend/audit/fields.js` | Every input/select/textarea in 18 real UI states: label source, type, constraints, initial value, options; every admin panel's load state | `field_completeness.csv` |
| `frontend/audit/controls.js` | Clicks every control (fresh page per control) and records whether anything happened | `control_audit.csv` |
| `frontend/audit/language.js` | Switches pages to Tamil and measures what changed | `language_audit.csv` |
| `backend/scripts/audit_api_matrix.py` | Calls every OpenAPI operation as 7 roles and checks the access decision | `api_verification.csv` |
| `backend/scripts/audit_consistency.py` | Recomputes every dashboard/list number with independent SQL | `data_consistency.csv` |
| `backend/scripts/audit_persistence.py` | Create → update → restart the API → verify | `workflow_results.csv` (workflow E) |
| Test suites | pytest (unit + integration on a disposable PostGIS database), Playwright (real stack), axe-core | §12 |

## 3. Completion metrics (computed)

| Metric | Count |
|---|---|
| Routes discovered / tested | 15 / 15 (14 pages + the 404 page); **15 PASS** |
| Role × route × viewport page loads | 315 (105 role/route cells × 3 widths) + 91 desktop/mobile re-check loads |
| Page sections (headings below h1) inspected | 54 |
| Form fields inspected | 116 in 18 UI states; 0 without a real label |
| Interactive controls clicked | 530 (460 with an effect, 70 with no observable effect — 70 classified benign, 0 unclassified); 13 sign-out buttons skipped on purpose |
| Admin panels opened | 10 (10 loaded with no HTTP error, banner or spinner) |
| API operations discovered / probed | 67 / 67 (63 in the 7-role matrix, **0 anomalies**; 4 auth operations covered by tests); every route referenced by a test: 67 of 67 |
| Data-consistency checks | 56 (0 mismatches) |
| Acceptance workflow steps | 30 in 5 workflows (0 failing) |
| Browser tests | 103 passed of 103 (local, real stack); hosted CI runs the same suite |
| Backend tests (local) | 509 passed, 16 Neo4j tests deselected (they run on hosted CI) |
| Defects found / fixed | 22 / 22 (P1: 4, P2: 11, P3: 7) |
| Open limitations | 8 (P2: 5, P3: 3) |

## 4. Routes, pages and sections

Role access was tested as anonymous, citizen, officer (own department), officer of another department, department administrator, state administrator and
system administrator. Columns: access = who may use the page; sections = headings below h1; controls = distinct controls clicked; fields = form fields inspected;
overflow = worst horizontal overflow in px over desktop 1440, tablet 820, phone 390.

| Route | Access | Sections | Controls | Fields | Overflow px | Result |
|---|---|---|---|---|---|---|
| `/` | everyone | 13 | 35 | 1 | 0 | PASS |
| `/login` | everyone | 0 | 11 | 2 | 0 | PASS |
| `/register` | everyone | 0 | 11 | 3 | 0 | PASS |
| `/schemes` | everyone | 13 | 26 | 3 | 0 | PASS |
| `/schemes/:id` | everyone | 1 | 18 | 9 | 0 | PASS |
| `/services` | everyone | 11 | 28 | 1 | 0 | PASS |
| `/services/:id` | everyone | 5 | 13 | 0 | 0 | PASS |
| `/documents` | everyone | 0 | 19 | 1 | 0 | PASS |
| `/complaints` | everyone | 1 | 21 | 9 | 0 | PASS |
| `/assistant` | everyone | 1 | 18 | 1 | 0 | PASS |
| `/dashboard` | citizen | 3 | 18 | 0 | 0 | PASS |
| `/officer` | officer|officer2|deptadmin|admin|sysadmin | 2 | 22 | 6 | 0 | PASS |
| `/admin` | admin|sysadmin | 2 | 22 | 71 | 0 | PASS |
| `/database-architecture` | admin|sysadmin | 2 | 98 | 9 | 0 | PASS |
| `/this-page-does-not-exist` | nobody (404) | 0 | 0 | 0 | 0 | PASS |

Redirect behaviour (observed): `/dashboard` → login (anonymous), `/officer` (staff), `/admin` (administrators); `/officer` → login (anonymous), `/dashboard` (citizen);
`/database-architecture` → login (anonymous), the user's own home page for citizens and staff. `/admin` shows an explicit *sign-in required* / *Access denied* message with no data (R08).
Per-route detail, observed behaviour per role and evidence are in `route_inventory.csv`.

## 5. Fields (textboxes, selects, checkboxes)

116 fields were inspected in their real UI states (login, registration, landing/scheme/service/document search and filters, the eligibility checker, complaint filing and
tracking, the assistant, officer filters/remarks/assignment, admin filters, SQL workspace, architecture explorer controls). Every field now has a real accessible name
(`label[for]`, wrapping label or `aria-label`); required fields are exposed to assistive technology; numeric fields carry min/max; free-text fields carry length limits that
match the backend schemas (title 3–200, description 10–5000, name ≤120, password ≥8, coordinates −90…90 / −180…180, eligibility facts bounded). Read-only values come straight from the API
(consistency audit, §9). Placeholders are never the only label. Validation evidence per form is in `field_completeness.csv`; invalid, empty, boundary and over-length inputs are exercised in
`audit_fixes.spec.ts` (eligibility), `complaints_assistant.spec.ts` (complaint form) and `test_api_*` (server-side 422s).

## 6. Controls

530 controls were clicked. 70 produced no observable effect; each was classified by hand-written rules (`control_audit.csv`, column *triage*): already-selected language toggle
(23), links to the page already open, already-active tabs/filters, search with an empty box, external link, empty required-field form submit, "New Chat" with nothing to reset, "Fit to screen"
when already fitted. **No dead control was found** (0 unclassified).

## 7. API (all 67 operations)

`api_verification.csv` lists the status each role receives for every operation. Rules checked: anonymous → 401 for protected endpoints; non-staff → 403 for staff endpoints;
non-admin → 403 for admin/architecture endpoints (department admins and officers included); public endpoints never refuse; no 5xx. Result: **63 operations, 0 anomalies.**
The four authentication operations (register, login, refresh, logout) are covered by `test_api_auth_catalog.py`/`test_security.py`. Mutating endpoints were probed with empty bodies or random ids so nothing was written.
The assistant endpoints are intentionally public with optional sign-in; conversation isolation was verified (anonymous → empty list/404, other users → 404, owner → 200).

## 8. Database and persistence

* Schema: 50 tables / 10 schemas / 513 columns / 77 foreign keys / 112 indexes (live, see the Database Architecture Explorer); migrations 002–008 + seed reproduce from scratch (hosted CI `db_verify`, Compose `make db-init`).
* **Persistence across a restart: PASS** — a new citizen filed a complaint, an officer assigned it and moved it to in-progress (checked in PostgreSQL after each step); the API process was
  killed and restarted; sign-in, status, officer remark, assignment, "my complaints", public tracking and the database row all survived.
* Demo database untouched by destructive operations; only labelled test records were added.

## 9. Data consistency

56 independent SQL recomputations match what the application reports (0 mismatches): public counts, catalogue totals and every category filter, admin counts,
verification breakdowns, per-department performance, the officer's department figures, a citizen's complaint list and timeline, plus structural integrity (no duplicate references, every complaint has a history row ending in its current status, no
officially-verified record without a source document, no officer assigned across departments, synthetic rows labelled). See `data_consistency.csv`.

## 10. Workflows

| Workflow | Steps | PASS | FAIL |
|---|---|---|---|
| A citizen | 15 | 15 | 0 |
| B officer | 5 | 5 | 0 |
| C department administrator | 1 | 1 | 0 |
| D state / system administrator | 5 | 5 | 0 |
| E persistence and recovery | 4 | 4 | 0 |

Step-by-step evidence (browser test titles or CLI tools) is in `workflow_results.csv`.

## 11. Visual, responsive and accessibility inspection

* Screenshots were captured from the running application (desktop and phone) for the landing page, schemes, scheme detail, citizen dashboard, officer console, admin console and all five Database Architecture tabs and were inspected; defects found that way (unstyled site, invented claims, clipped officer table) were fixed.
* No page overflows horizontally at 1440, 820 or 390 px (sweep); no broken images; no dead links; no console errors or failed API requests other than cancelled link prefetches (harmless).
* axe-core (WCAG 2.0/2.1 A/AA, serious+critical) passes in all 16 scans (public pages, signed-in forms, admin console, five architecture tabs); keyboard operation and focus rings are tested.

### Language (measured)

The Tamil toggle works and persists after reload, but only some pages are translated beyond the navigation:

| Page | Text nodes | Tamil % (English mode) | Tamil % (Tamil mode) | Nodes changed | Persists |
|---|---|---|---|---|---|
| `/` | 98 | 0.2% | 1% | 2 | yes |
| `/login` | 16 | 3.9% | 88.4% | 12 | yes |
| `/register` | 18 | 3.1% | 77% | 13 | yes |
| `/schemes` | 101 | 16.6% | 18.9% | 7 | yes |
| `/schemes/:id` | 40 | 5.4% | 14.8% | 7 | yes |
| `/services` | 82 | 9.8% | 12.8% | 7 | yes |
| `/documents` | 23 | 2.2% | 28.7% | 7 | yes |
| `/complaints` | 21 | 2.2% | 54% | 12 | yes |
| `/assistant` | 22 | 0.9% | 12% | 7 | yes |

Tamil strings in the interface are **not professionally reviewed**; data-driven Tamil names (`name_ta`) come from the dataset. See R01.

## 12. Test commands and results

| Check | Command | Result |
|---|---|---|
| Backend (unit + integration, PostGIS) | `cd backend && TEST_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres TEST_POSTGIS=1 pytest tests -q --deselect tests/integration/test_knowledge_graph.py` | **509 passed**, 16 deselected (Neo4j not running locally) |
| Ruff / mypy | `ruff check app scripts etl knowledge_graph ai tests` · `mypy app scripts etl knowledge_graph ai` | clean (hosted CI enforces both) |
| Frontend types / lint / build | `npx tsc --noEmit` · `npx next lint` · `npm run build` | clean |
| Browser (Playwright, real stack) | `NEXT_DIST_DIR=.next-e2e E2E_PG_PORT=5432 E2E_PG_USER=postgres npx playwright test` | **103 passed of 103** |
| API role matrix | `python -m scripts.audit_api_matrix out.csv http://127.0.0.1:8000` | 63 operations, 0 anomalies |
| Consistency | `python -m scripts.audit_consistency --dsn postgresql://…/mygovt_dev_demo` | 56 checks, 0 mismatches |
| Persistence | `python -m scripts.audit_persistence create|verify` (API restarted in between) | PASS |
| Hosted CI | GitHub Actions (backend incl. Neo4j, Playwright, frontend, security, SQL provenance, 4 image builds, Compose + demo smoke) | see the final summary for the run id |

## 13. Defects found and fixed

| ID | Sev | Area | Defect | Fix | Regression test |
|---|---|---|---|---|---|
| D01 | P1 | Eligibility | The eligibility checker could not be opened from the UI: its modal was rendered only when a state variable was set, and nothing ever set it. | New inline EligibilityChecker on the scheme detail page (labelled fields, client validation, per-criterion results, demo-rule banner). | audit_fixes.spec 'eligibility checker' (5 tests) |
| D02 | P1 | Services | Every service card linked to /services/:id, which did not exist (404). | Added the service detail page (description, honest fee/time section, documents, apply link, source). | audit_fixes.spec 'service details' (2 tests) |
| D03 | P2 | Schemes | Category options were hard-coded; 9 of 11 returned nothing. | Options now come from GET /schemes/categories/list. | audit_fixes.spec + test_api_auth_catalog category test |
| D04 | P2 | Services | Category pills were hard-coded; 6 of 8 returned nothing and no categories endpoint existed. | New GET /services/categories/list; pills built from it. | audit_fixes.spec + test_api_auth_catalog category test |
| D05 | P2 | Eligibility API | Accepted age -5, income -100, family size 0, oversized strings. | Pydantic bounds and length limits (422). | test_api_auth_catalog (11 invalid + boundary cases) |
| D06 | P2 | Eligibility UI | Result colours used dynamically composed Tailwind class names (not generated, so the result box was unstyled); labels not associated with inputs; no dialog semantics. | Replaced by the new component with fixed class maps and real label/for associations. | audit_fixes.spec |
| D07 | P2 | Layout | Horizontal scrolling of 33 px and 3 px at 390 px width (search form, long department badge). | Wrapping forms, min-w-0, truncating badges with tooltips. | audit_fixes.spec 'no horizontal scrolling on a phone' (4 pages) |
| D08 | P2 | Accessibility | Search inputs had no accessible name (placeholder only). | aria-label on each; role=search on forms. | audit_fixes.spec 'search boxes have accessible names' |
| D09 | P2 | Admin data panels | Quality scores rendered as 10000% (0-100 values multiplied by 100 again); scores presented as measurements although they are seeded values. | Correct scale, clamped; disclaimer that the scores are recorded in the registry, not computed. | audit_fixes.spec 'dataset quality scores...' |
| D10 | P3 | Accessibility | The query textarea had no accessible name. | aria-label added. | audit_fixes.spec |
| D11 | P3 | Forms | Required fields were marked with an asterisk only; not exposed to assistive technology. | aria-required on Subject and Description (custom messages kept). | audit_fixes.spec |
| D12 | P3 | Architecture page | Protected API calls were made (and failed 401/403) before the role guard redirected. | Fetches wait for a permitted user. | audit_fixes.spec 'no protected API calls before sign-in' |
| D13 | P3 | Accessibility | Heading levels skipped (h1 straight to h3). | Section headings added (screen-reader only). | route sweep re-run: 0 skips |
| D14 | P3 | Error pages | Default unstyled framework 404 page. | Styled not-found page with links back. | audit_fixes.spec 'unknown pages show a styled 404' |
| D15 | P2 | API docs | The documented documentation URL returned 404 (docs live at /api/docs). | Development-only redirects /docs -> /api/docs, /redoc -> /api/redoc; guide corrected. | test_ops_endpoints docs alias test |
| D16 | P1 | Styling | Tailwind CSS was never compiled (no postcss.config.js): every page shipped unstyled. | Added postcss.config.js; component classes moved into @layer components. | full browser suite on the styled build (103 tests) |
| D17 | P2 | Accessibility | WCAG contrast failures (ghost buttons, saffron buttons, grey text) once styles applied. | Palette and classes corrected. | accessibility.spec (11 scans) + architecture.spec (5 scans) |
| D18 | P1 | Authorization | Any officer could read and change complaints of any department. | Department scoping in the service layer; unlinked staff refused. | test_api_complaints scoping tests; staff_workflows.spec |
| D19 | P2 | Honesty | Claimed to be an official government platform, showed invented amounts and a scheme not in the data, dead footer links. | Truthful copy, dataset-only schemes, real links. | public.spec 'no invented figures' |
| D20 | P2 | Health | A blocking MinIO check starved the event loop, so Redis was reported unhealthy when MinIO was absent. | MinIO probe runs in a thread; every check is time-bounded. | test_health_isolation (fails on the old code) |
| D21 | P3 | Architecture page | PostgreSQL's long Linux version() string was used as a display name and overflowed phone screens. | Short parsed name; badges truncate. | test_architecture_logic + architecture.spec phone test |
| D22 | P3 | Demo data | Every open demo complaint was past target (data dated from a fixed reference time). | New demo builds date data relative to now with recent open complaints (existing demo database untouched). | test_demo_env 'believable board' |

Files changed by the audit are in the commit history of the branch (frontend pages/components, `backend/app/api/v1/{services,architecture}.py`, `schemas/schemes.py`, `services/other_services.py`, `core/health.py`, `main.py`, the audit tools, tests and docs).

## 14. Remaining defects and limitations

| ID | Sev | Area | Limitation | Needed to close |
|---|---|---|---|---|
| R01 | P2 | Language | Tamil coverage is uneven (measured): landing page changes 2 of 98 text nodes; schemes/services/documents/assistant change only the navigation chrome; translations are unreviewed. | Needs a human translator; not machine-translated on purpose. |
| R02 | P2 | Admin | No UI to create or edit schemes/services (the catalogue is read-only apart from the verification queue). | Out of scope for this sprint; would also need an approval workflow. |
| R03 | P2 | Evidence | Evidence upload returns 503 by design (object storage not implemented). | Choose and verify an object-storage image first. |
| R04 | P2 | Government data | All government records are provisional; no official source evidence; fees/timings/eligibility rules unconfirmed. | Needs a human reviewer with the official documents. |
| R05 | P3 | Assistant | No LLM: answers are extractive over recorded records; anonymous chats cannot be re-opened (by design). | Optional; needs an API key. |
| R06 | P3 | Infrastructure | Redis, MinIO and Neo4j are not running in the local demo; no real boundary polygons are loaded. | Docker Compose runs Redis/Neo4j; boundaries need authoritative data. |
| R07 | P2 | Security | Public-deployment items remain open: in-process rate limits, refresh tokens in localStorage, no MFA, no password reset or e-mail verification, no TLS. | Not required for the university demo; mandatory before any public use. |
| R08 | P3 | Sweep note | The sweep flags /admin as 'rendered' for non-admins: it renders an explicit 'Access denied'/'sign-in required' message and no data (tested, API also refuses). | False positive of the generic check; no change. |

### Government-data verification (separate gate, unchanged)

`official_verified` 0 · `externally_referenced` 1 (PM-Kisan) · `provisional` 76 · ingested documents `unverified`. Fees, processing times, GO references, district codes, eligibility rules (the 8 labelled `[DEMO RULE]`s are illustrations, not criteria),
authorities and boundaries have **not** been checked against official documents. Passing these audits proves the software shows that honestly; it proves nothing about the accuracy of the government information.

## 15. Completion matrix

| Area | Status | Basis |
|---|---|---|
| Pages and role access | PASS | §4 |
| Forms and fields | PASS | §5 |
| Controls | PASS | §6 |
| API and authorization | PASS | §7 |
| Persistence, consistency | PASS | §8–9 |
| Workflows A–E | PASS | §10 |
| Responsive, accessibility | PASS | §11 |
| Language (Tamil) | **PARTIAL** | R01 |
| Admin catalogue editing | **NOT IMPLEMENTED** | R02 |
| Evidence upload | **NOT IMPLEMENTED (503 by design)** | R03 |
| Government-data verification | **UNRESOLVED** | R04 |
| Public-deployment security | **OPEN** | R07 |

## 16. Reproduce

```bash
make demo            # or docs/demo.md section 1B without Docker
cd frontend && API=http://127.0.0.1:8000 node audit/sweep.js out && node audit/fields.js out && node audit/controls.js out && node audit/language.js out
cd backend && python -m scripts.audit_api_matrix api.csv http://127.0.0.1:8000 && python -m scripts.audit_consistency --dsn postgresql://postgres@localhost:5432/mygovt_dev_demo
python -m scripts.audit_persistence create --state s.json   # restart the API, then:  python -m scripts.audit_persistence verify --state s.json
```
