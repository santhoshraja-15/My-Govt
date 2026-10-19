# MyGovt — demonstration guide (university project)

This guide runs the finished application with a **clearly labelled demonstration dataset** and walks through a 10-minute presentation.
Nothing here is official government data: the catalogue records are *Provisional*, and the demo complaints, officers and accounts are
*synthetic* (`is_synthetic`, titles prefixed `[SYNTHETIC]`, e-mails on `@demo.example`).

## 1. Start it

### A. Docker Compose (recommended, works on Windows with Docker Desktop)

```bash
cp .env.example .env            # then give every secret a value (compose refuses to start otherwise)
make demo                       # = docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
                                #   + python -m scripts.demo_env inside the backend container
make demo-check                 # optional: 21 live API checks of the scenario below
```

Without `make`:

```powershell
docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d --build
docker compose exec -T backend sh -c 'python -m scripts.demo_env --admin-dsn postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@postgres:5432/postgres'
```

Open **http://localhost:3000** (API docs: http://localhost:8000/api/docs). Stop with `docker compose down` (add `-v` to delete the data).

Re-running `make demo` is safe: the script is idempotent; add `--reset` (in the `demo_env` command) to rebuild the demo database.

### B. Without Docker (what was used to develop this)

Needs PostgreSQL 16 with the PostGIS and pgvector extensions, Python 3.12 and Node 22.

```bash
cd backend && pip install -r requirements-ci.txt
python -m scripts.demo_env --admin-dsn postgresql://postgres@localhost:5432/postgres
# API (demo database, demo complaints included in staff lists/statistics):
POSTGRES_DB=mygovt_dev_demo DEMO_INCLUDE_SYNTHETIC=true APP_CORS_ORIGINS=http://localhost:3000 FEATURE_GRAPH=false \
  python -m uvicorn app.main:app --port 8000
# frontend (the API URL is baked in at build time):
cd ../frontend && npm ci && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build && npx next start -p 3000
```

(`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_HOST` must match your server. Redis, Neo4j and MinIO are optional: the platform reports them
as unhealthy/disabled and everything below still works.)

## 2. Demo accounts

Fixture credentials of the throw-away demo database only. Never reuse them anywhere else. Change the password with `DEMO_PASSWORD` when running `demo_env`.

| Role | Login | Password | Lands on |
|---|---|---|---|
| Citizen | `citizen@demo.example` | `Demo@12345` | `/dashboard` |
| Officer (Revenue Department) | `officer@demo.example` | `Demo@12345` | `/officer` |
| Officer (Health & Family Welfare) | `officer2@demo.example` | `Demo@12345` | `/officer` |
| Department admin (Revenue) | `deptadmin@demo.example` | `Demo@12345` | `/officer` |
| State admin | `admin@demo.example` | `Demo@12345` | `/admin` |
| System admin | `sysadmin@demo.example` | `Demo@12345` | `/admin` |

You can also register a new citizen on `/register`.

## 3. Presentation script (≈10 minutes)

1. **Landing page** (`/`). Point out the live counts (12 schemes, 38 districts, 10 services, 17 departments) and the honest footer: *university demonstration project, not an official website*.
2. **Schemes and services** (`/schemes`, `/services`). Search and filter (category and level lists come from the data; every one returns results); open a service to see the honest *fees unconfirmed* section and the official apply link; every card carries a verification badge — all **Provisional** (PM-Kisan: *External source*). Say why: no record has yet been checked against an official document; the platform refuses to call anything "Verified" without evidence.
3. **Eligibility.** Open *Kalaignar Magalir Urimai Thogai* and press **Check my eligibility**: the banner says the criteria are **demonstration rules**. Answer *Female* and income *180000* → "appear to meet the recorded criteria" with a per-criterion table; *Male* → "do not meet"; income 250000 is the boundary (meets), 250001 does not; leave answers blank → "not enough information" (never guessed). Invalid answers (age −5) are explained next to the field. It is an indicative check, not an application.
4. **Citizen** (`citizen@demo.example`). Dashboard: totals, past-target count, status donut chart, six complaints in different states (every state of the lifecycle), all labelled `[SYNTHETIC]`. File a **new complaint** on `/complaints` (pick a category, e.g. *Garbage / Solid Waste Collection*), note the reference `MYG-…`, refresh the page — it is still there (stored in PostgreSQL). Use *Track Status* with the reference.
5. **Officer** (sign out → `officer@demo.example`). The console shows only the Revenue Department's complaints. Open one in *Classified* state → **Assign to me** → add a remark → move it to **In progress**. Notice only legal next states are offered; an illegal jump is refused by the API (409).
6. **Back to the citizen.** The new status and the officer's remark appear in the complaint history; the dashboard counters changed.
7. **Isolation.** As the Revenue officer, `GET /api/v1/complaints/{id}` of a Health complaint → **403**; a citizen cannot open another citizen's complaint (403) nor `/officer` (redirected).
8. **Admin** (`admin@demo.example`). Overview (live counts from the database, the *demonstration mode* notice), complaints with overdue / unassigned filters, department performance, **verification queue** (what still needs official evidence), audit log, service health.
9. **Database Architecture** (admin → *Database Architecture* in the top navigation): the live architecture diagram, the ER diagram of the 50 real tables (search *complaint*, select `complaints.complaint`, tick *Focus on selection*), the relational schema, example queries you can run and explain, and which advanced database concepts exist and which do not. See [database-architecture.md](database-architecture.md).
10. **Assistant** (`/assistant`). Ask *"What is the Kalaignar Magalir Urimai Thogai?"* — answers cite the records and show their verification status; ask something outside the data (*"Who won the cricket match?"*) — it abstains instead of inventing an answer.
11. **Close** with the limitations below.

## 4. What is real and what is demonstration

| Real, and tested | Demonstration only |
|---|---|
| Registration/login/logout, Argon2 passwords, JWT, roles, lockout, rate limits | The six `@demo.example` accounts and their shared password |
| Complaint filing/tracking, SLA targets, status state machine, assignment, department scoping, audit log | 86 synthetic complaints (80 across departments + 6 for the demo citizen), 16 synthetic officers |
| Scheme/service catalogue, eligibility engine, verification governance | The 8 eligibility rules (labelled `[DEMO RULE]`, source `DEMO RULE - not an official criterion`) |
| Dashboards computed from database rows | `DEMO_INCLUDE_SYNTHETIC=true` mixes labelled synthetic rows into staff lists and statistics (off by default) |

## 5. Known limitations (disclose them)

* Government records are **Provisional**; fees, timings, GO references, district codes and eligibility rules are not officially confirmed.
* Evidence upload returns *503 — not saved* (storage is not implemented). No OCR. No map picker (coordinates only).
* No officer self-registration; officers are created by seed scripts. There is no admin UI for editing schemes/services (read-only catalogue plus the verification queue).
* Tamil: navigation and scheme names are bilingual; many page texts are English and the Tamil is unreviewed.
* Security for a public deployment is **not** finished: in-process rate limiting, refresh tokens in `localStorage`, no MFA, no password reset/e-mail verification, no TLS in this setup. This is a local demonstration.
* The assistant uses retrieval over the loaded records; without an LLM key it answers extractively (no free-form generation).
