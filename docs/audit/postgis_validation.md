# PostGIS integration gate

**Date:** 2026-10-18 · **Branch:** `audit/tn-data-verification`

## Environment actually used (and its limits)

| Item | Value |
|---|---|
| PostgreSQL | 16.15 (conda-forge build, Windows), disposable instance on port 54329 |
| PostGIS | **3.6.2** — OSGeo Windows bundle `postgis-bundle-pg16-3.6.2x64.zip` (md5 `6730107131c29b7ff9a36702f736007b`, verified against the published `.md5`), files copied into the conda Postgres; GEOS 3.14.1, PROJ 8.2.1 |
| pgvector | 0.x from conda-forge (vector.dll) |
| Not used | The project's own image `postgis/postgis:16-3.4` — Docker is unavailable on this machine |

**Caveat:** PostGIS 3.6.2 / a hand-assembled Windows install is not the project's deployment image
(3.4). Behaviour of the functions used here (`ST_Covers`, `ST_Contains`, `ST_DWithin`,
`ST_DistanceSphere`, GIST) is stable across 3.4–3.6, but the gate should be re-run against the
real image in CI (`TEST_POSTGIS=1`), and this report updated.

## Result

`TEST_POSTGIS=1 pytest tests -q` → **266 passed** (exit 0), of which 18 are spatial
(`tests/integration/test_postgis_spatial.py`). `python -m scripts.db_verify` (no `--no-postgis`)
→ OK; the unmodified `001_schema.sql` applies with the real extension.

Verified on real PostGIS:

* extension installed; geometry columns have SRID 4326 and the expected types
  (MULTIPOLYGON for boundaries, POINT for `location`); an SRID-3857 write is rejected;
* all GIST indexes created, and the district index is chosen for point-in-polygon;
* `resolve_jurisdiction`: interior, outside, ward → local body → taluk → district hierarchy,
  taluk-only and local-body-only levels, lon/lat swapped, out-of-range coordinates;
* complaint-location trigger: fills `location` + jurisdiction on INSERT and when coordinates are
  UPDATEd, keeps an explicit `district_id`, ignores NULL coordinates;
* API: `/gis/resolve-jurisdiction` (200/404/422) and complaint submission attribute jurisdiction;
* nearby facilities: ordering, `facility_type` filter, radius, distance in km within 1 % of a
  haversine oracle, coordinates returned.

## Defects found by the real run (and fixed in migration 005)

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1 | Points exactly on a shared border or polygon vertex resolved to **no district** (`ST_Contains` excludes the boundary) | border (80.5,13.25) and vertex (80.0,13.0) → NULL | `ST_Covers` |
| 2 | Overlapping polygons gave an arbitrary answer (physical row order) | point in overlap of A and C returned A | smallest covering polygon, ties by id |
| 3 | Out-of-range coordinates produced a row of NULLs | lon 200 | returns no row |
| 4 | Nearby-facility query seq-scanned: `location::geography` cannot use the geometry GIST index | `EXPLAIN` with `enable_seqscan=off` still showed Seq Scan | expression GIST index `idx_facility_geog` |

Without migration 005 five of the 18 tests fail; with it all pass (checked).

## Still NOT verified

* **Geographic correctness.** The repository contains no authoritative boundary polygons. Tests
  use synthetic boxes laid on real district rows. Whether a real Chennai coordinate maps to the
  real Chennai district is unknown until official boundary data is loaded.
* Query plans at realistic volume (tests use a handful of rows and force `enable_seqscan=off` to
  prove index *usability*, not that the planner prefers it).
* The boundary tie-break (a point on the A|B edge belongs to *one* of them) is a policy
  choice, not a cadastral truth.
* Behaviour on the project's `postgis/postgis:16-3.4` image.
