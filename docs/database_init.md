# Database initialisation

## Order (`make db-init`, clean database only)

| Step | Target | File | Re-runnable? |
|---|---|---|---|
| 1 | `make schema` | `database/schema/001_schema.sql` | No - clean DB only |
| 2 | `make migrate-sql` | `database/migrations/002_provenance_and_audit_fixes.sql` | Yes (`IF NOT EXISTS`) |
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

## Known limitations

* **Provenance gap:** all 17 departments and 10 services (and 38 districts, which have no such column)
  are marked `official_verified` but carry no `source_document_ref`. 11 schemes carry the reference
  asserted by the curated JSON (GO numbers / guideline names); those were **not** independently
  re-checked against the issuing documents. `seed.py` reports the gap as WARN rather than rewriting
  the status; decide whether to demote to `provisional` until references are added.
* LGD codes come from `data/validated/tn_districts_master_2026.json`; they were not re-verified
  against the Local Government Directory here.
* Spatial objects (`resolve_jurisdiction`, location trigger, GIST indexes) need a real PostGIS run.
