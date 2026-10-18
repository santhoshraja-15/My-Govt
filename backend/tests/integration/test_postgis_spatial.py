"""Spatial behaviour that REQUIRES a real PostGIS server.

These tests are written against PostGIS but have never been executed in the environment where
this milestone was developed (no PostGIS available). They are skipped by default with the reason
"BLOCKED" (see tests/conftest.py). To run them:

    TEST_ADMIN_DSN=postgresql://postgres:...@host:5432/postgres TEST_POSTGIS=1 pytest -m postgis

against a server using the postgis/postgis image (the project's docker/postgres image). Until
that run is recorded, resolve_jurisdiction, the complaint-location trigger, GIST index creation
and the nearby-facilities query must be considered UNVERIFIED.
"""
import pytest

pytestmark = [pytest.mark.db, pytest.mark.postgis]

API = "/api/v1"
BOX = "MULTIPOLYGON(((80.0 13.0, 80.5 13.0, 80.5 13.5, 80.0 13.5, 80.0 13.0)))"
INSIDE = (80.25, 13.25)    # lon, lat
OUTSIDE = (78.0, 10.0)


@pytest.fixture
async def boundaries(conn):
    """A synthetic test district/taluk polygon (inside the real Chennai district row for FK purposes)."""
    did = await conn.fetchval("SELECT district_id FROM administration.district WHERE district_code='TN-CHN'")
    await conn.execute("UPDATE administration.district SET geometry = ST_GeomFromText($2, 4326) WHERE district_id=$1", did, BOX)
    tid = await conn.fetchval(
        "INSERT INTO administration.taluk (district_id, name, geometry) VALUES ($1,'Spatial-Test-Taluk', ST_GeomFromText($2,4326)) "
        "RETURNING taluk_id", did, BOX)
    yield did, tid
    await conn.execute("DELETE FROM administration.taluk WHERE taluk_id=$1", tid)
    await conn.execute("UPDATE administration.district SET geometry = NULL WHERE district_id=$1", did)


async def test_resolve_jurisdiction_function(conn, boundaries):
    did, tid = boundaries
    inside = await conn.fetchrow("SELECT * FROM administration.resolve_jurisdiction($1,$2)", *INSIDE)
    assert inside["district_id"] == did and inside["taluk_id"] == tid
    outside = await conn.fetchrow("SELECT * FROM administration.resolve_jurisdiction($1,$2)", *OUTSIDE)
    assert outside["district_id"] is None


async def test_complaint_location_trigger_fills_geometry_and_jurisdiction(conn, boundaries, make_citizen):
    did, tid = boundaries
    c = await make_citizen()
    ref = await conn.fetchval(
        "INSERT INTO complaints.complaint (citizen_id, title, description, latitude, longitude) "
        "VALUES ($1,'t','d',$2,$3) RETURNING complaint_ref", c["user"]["citizen_id"], INSIDE[1], INSIDE[0])
    row = await conn.fetchrow("SELECT location IS NOT NULL AS has_geom, ST_X(location) AS x, ST_Y(location) AS y, "
                              "district_id, taluk_id FROM complaints.complaint WHERE complaint_ref=$1", ref)
    assert row["has_geom"] and (row["x"], row["y"]) == INSIDE
    assert (row["district_id"], row["taluk_id"]) == (did, tid)


async def test_gist_indexes_exist(conn):
    rows = await conn.fetch("SELECT indexname, indexdef FROM pg_indexes WHERE indexname = ANY($1)",
                            ["idx_district_geom", "idx_taluk_geom", "idx_block_geom", "idx_lb_geom",
                             "idx_ward_geom", "idx_facility_geom", "idx_complaint_geom"])
    assert len(rows) == 7 and all("USING gist" in r["indexdef"] for r in rows)


async def test_resolve_jurisdiction_endpoint(client, boundaries):
    r = await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": INSIDE[1], "lon": INSIDE[0]})
    assert r.status_code == 200 and r.json()["district_name"] == "Chennai" and r.json()["resolved_level"] == "taluk"
    out = await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": OUTSIDE[1], "lon": OUTSIDE[0]})
    assert out.status_code == 404


async def test_nearby_facilities_orders_by_distance_and_filters_radius(client, conn):
    ids = []
    for name, lon, lat in (("Near PHC", 80.2707, 13.0827), ("Far PHC", 80.40, 13.30), ("Distant PHC", 77.0, 11.0)):
        ids.append(await conn.fetchval(
            "INSERT INTO services.government_facility (name, facility_type, location) "
            "VALUES ($1,'phc', ST_SetSRID(ST_MakePoint($2,$3),4326)) RETURNING facility_id", name, lon, lat))
    try:
        r = await client.get(f"{API}/gis/facilities", params={"lat": 13.0827, "lon": 80.2707, "radius_km": 50, "facility_type": "phc"})
        names = [f["name"] for f in r.json()]
        assert r.status_code == 200 and names == ["Near PHC", "Far PHC"]
        assert r.json()[0]["distance_km"] < r.json()[1]["distance_km"]
    finally:
        await conn.execute("DELETE FROM services.government_facility WHERE facility_id = ANY($1)", ids)
