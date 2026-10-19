# Database Architecture Explorer

**Route:** `/database-architecture` (tabs: `?tab=architecture | er | schema | implementation | advanced`)
**Who can open it:** `state_admin` and `system_admin` only. The button *Database Architecture* appears in the main navigation and in the admin console sidebar for those roles; citizens, officers, department admins and anonymous visitors do not see it, are redirected away from the URL, and the API answers them 401/403.

The page explains the database MyGovt actually uses. Nothing is a hand-drawn diagram or a frontend constant: every number, table, column, relationship and index is read from the running PostgreSQL catalog and from the backend source tree when the page loads.

## Tabs

| Tab | What it shows | Source of truth |
|---|---|---|
| **Architecture** | Interactive diagram of frontend → FastAPI → service layer → PostgreSQL (+ PostGIS, pgvector) and the optional Neo4j, Redis, MinIO. Select a box for purpose, implementation location, tables/endpoints involved, connections and live availability. | `GET /api/v1/architecture/components` (health checks + `pg_extension`) |
| **ER Diagram** | One node per table, one edge per enforced foreign key, grouped by schema/domain. Zoom, pan, drag, minimap, fit, reset, search (table or column), schema filter chips, compact mode, cardinality labels, *Focus on selection*, optional dashed *conceptual links*. Selecting a table highlights its neighbours and opens its detail panel. | `/tables`, `/relationships` (`pg_class`, `pg_attribute`, `pg_constraint`, `pg_index`) |
| **Relational Schema** | `TABLE(PK:id, FK:other_id, column, …)` for every relation, with unique/not-null/check constraints and delete rules, plus the normalization analysis. | `/schema`, `/normalization` |
| **Implementation** | Searchable table browser: columns with types and PK/FK/UQ/NN flags, constraints, indexes, tables referenced / referencing, backend source files that mention the table, generated example joins, a sample of rows for public catalogue tables only. Lists the baseline schema, migrations and seed files, and ten curated read-only example queries that can be run and explained (query plan). | `/tables/{schema}/{table}`, `/implementation`, `/examples/{id}/run|explain` |
| **Advanced Concepts** | Views, functions, triggers, transactions, indexing, query plans, PostGIS, pgvector, Neo4j, Redis, integrity constraints, audit/history. Each is **Implemented** with real examples, or **Not implemented** with the reason. | `/advanced` |

## API (all `GET`, read-only, admin only)

`/api/v1/architecture/` + `overview`, `components`, `tables`, `tables/{schema}/{table}`, `relationships`, `schema`, `normalization`, `advanced`, `implementation`, `examples/{id}/run`, `examples/{id}/explain`.

## How the metadata is retrieved

* **Tables, columns, defaults, keys, constraints, indexes, views, functions, triggers, extensions:** PostgreSQL system catalogs (`pg_class`, `pg_attribute`, `pg_attrdef`, `pg_constraint`, `pg_index`, `pg_trigger`, `pg_proc`, `pg_views`, `pg_extension`). PostGIS system tables (extension members) and the `public` schema are excluded.
* **Cardinality:** a foreign key is *one-to-one* when its columns are themselves unique (primary key, unique constraint or plain unique index), otherwise *one-to-many*; *mandatory* vs *optional* follows NOT NULL on the referencing columns. Many-to-many is reported only for junction tables whose primary key consists solely of foreign keys.
* **Conceptual (inferred) relationships:** columns named `*_id` that match another table's single-column primary key but have **no** foreign key are listed separately, drawn dashed, and labelled "not enforced by the database".
* **Backend usage:** a static scan of `backend/app`, `scripts`, `etl`, `knowledge_graph`, `ai` for `schema.table`.
* **Availability:** PostgreSQL is *active* when the explorer's own session read the catalog; Neo4j/Redis/MinIO come from the health checks (*Active*, *Unavailable*, *Disabled by design*). Optional services that are not running are reported, never hidden, and nothing fails.
* **Normalization:** structural facts only (primary key present, composite candidate keys, JSON/array/tsvector columns). Second normal form is automatic for single-column candidate keys. **Third normal form is never claimed** — functional dependencies are not stored in the catalog; "possible redundancy" hints are recommendations to review.

## Safety

* Admin only (server-side `require_role`), every table view and example run is written to the audit log.
* No secrets: no connection strings, environment variables or tokens are returned (tested).
* Row data: only an allow-listed set of public catalogue tables shows up to five rows, with sensitive-looking (`password`, `token`, `hash`, `email`, `phone`, `address`, …) and bulky (vector, geometry, tsvector) columns removed. Identity, complaint, audit and AI tables never show rows.
* No user-supplied SQL: example queries are fixed server-side, run in a read-only transaction with a 3-second statement timeout, and `EXPLAIN` does not execute the statement. Identifiers in generated SQL are quoted.

## Measured on the demonstration database

50 tables in 10 schemas, 513 columns, 77 enforced foreign keys (+5 conceptual), 112 indexes (B-tree, GIN, GiST, HNSW), 4 views (2 project + 2 PostGIS), 13 triggers, 7 project functions, extensions `plpgsql, postgis 3.6.2, vector 0.8.6, pg_trgm, pgcrypto, btree_gist`. (Counts are live; they change with the schema.)

## Limitations

* The ER layout is computed (schema-grouped grid); dragged positions are not saved.
* 50 tables do not fit one screen legibly: use search, schema chips or *Focus on selection*.
* Redis and MinIO are shown as optional and unused by any feature; Neo4j is a one-way projection that is disabled unless configured.
* No stored procedures (`CALL`) exist in the project, so that concept is shown as *Not implemented*.
* Cardinality is derived from constraints; business-rule cardinality that is not constrained (e.g. "a citizen should have at most N complaints") cannot be shown.

## Tests

* Backend: `backend/tests/integration/test_api_architecture.py` (23 tests: authorization for 5 roles on every endpoint, counts/FKs/columns equal the real catalog, no secrets, sample restrictions, read-only runner, audit) and `backend/tests/unit/test_architecture_logic.py` (8).
* Browser: `frontend/e2e/architecture.spec.ts` (21 tests: navigation and access, real counts, diagrams, search/filter/focus/reset, relational schema, implementation browser, example queries, advanced concepts, error/retry, phone and tablet widths, keyboard, axe on every tab).
