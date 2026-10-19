# Database initialisation

## Order (`make db-init`, clean database only)

| Step | Target | File | Re-runnable? |
|---|---|---|---|
| 1 | `make schema` | `database/schema/001_schema.sql` | No - clean DB only |
| 2 | `make migrate-sql` | every `database/migrations/NNN_*.sql` in order (002 provenance, 003 API-schema alignment, 004 verification governance) | Yes (idempotent) |
| 3 | `make seed` | `database/seeds/002_verified_seed_data.sql` via `backend/scripts/seed.py` | Yes (upserts) |

`database/seeds/001_seed_data.sql` is a **legacy, unaudited** seed and is intentionally not applied.
`make migrate` (alembic) has no revisions yet; use `migrate-sql` until Alembic is introduced.

## `python -m scripts.seed`

* `--dry-run` apply + check, roll back. `--verify-only` checks only. `--strict` WARN => failure.
* Exit codes: `0` ok, `1` a check failed (seed rolled back), `2` preflight failed (schema/migration missing).
* Connection: `--dsn` / `SEED_DATABASE_URL` / `POSTGRES_*` env vars. Nothing is hard-coded.
* Checks: unique constraints, 38 districts, unique `lgd_code` matching `data/validated`, scheme
  `source_document_ref`/`verification_status` matching the validated JSON, dataset checksums
  well-formed and equal to the SHA-256 of the files on disk, sequences advanced past seeded ids,
  no synthetic sources, and **provenance gaps** (see below).

## `python -m scripts.db_verify` / `make db-verify`

Builds a throw-away `mygovt_test_*` database, runs schema -> migration (x2) -> seed (x2) -> negative
constraint probes, then drops it. Refuses non-`mygovt_test_` names. `--no-postgis` supports servers
without PostGIS (relational checks only; spatial behaviour unverified).

## Verification status

All curated records load as `provisional`; none is `official_verified` because no official document
evidence is recorded (see `docs/audit/milestone_2_validation.md`). Status changes are logged in
`system.verification_status_log`, and `official_verified` requires a `source_document_ref`.

## Running the test-suite

```
cd backend
TEST_ADMIN_DSN=postgresql://postgres@localhost:5432/postgres python -m pytest tests -q -rs
```
`TEST_ADMIN_DSN` must point at a DISPOSABLE server; the tests create/drop `mygovt_test_*` databases.
PostGIS tests need `TEST_POSTGIS=1` and a PostGIS server.

## Known limitations

* **Provenance:** the 11 scheme references (GO numbers / guideline names) come from the curated
  JSON and were **not** independently checked against the issuing documents; they are retained for
  follow-up only and the schemes are `provisional`.
* LGD codes come from `data/validated/tn_districts_master_2026.json`; they were not re-verified
  against the Local Government Directory here.
* Spatial objects (`resolve_jurisdiction`, location trigger, GIST indexes) need a real PostGIS run.
