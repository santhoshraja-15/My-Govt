"""Spatial behaviour that REQUIRES a real PostGIS server.

Skipped by default with reason "BLOCKED" (tests/conftest.py). Run with:

    TEST_ADMIN_DSN=postgresql://postgres:...@host:5432/postgres TEST_POSTGIS=1 pytest -m postgis

Geometry used here is SYNTHETIC (axis-aligned boxes) laid over real district rows only to satisfy
foreign keys. It validates the SQL logic, NOT the accuracy of any real Tamil Nadu boundary: no
authoritative boundary polygons are loaded in this repository, so geographic correctness of
jurisdiction mapping remains UNVERIFIED.
"""
import math

import pytest

pytestmark = [pytest.mark.db, pytest.mark.postgis]

API = "/api/v1"


def box(lon0, lat0, lon1, lat1):
    return (f"MULTIPOLYGON((({lon0} {lat0},{lon1} {lat0},{lon1} {lat1},{lon0} {lat1},{lon0} {lat0})))")


A = box(80.0, 13.0, 80.5, 13.5)        # district A (Chennai row)
B = box(80.5, 13.0, 81.0, 13.5)        # district B, shares the edge lon=80.5 with A (Coimbatore row)
C = box(80.2, 13.2, 80.4, 13.4)        # district C, lies INSIDE A (Madurai row) -> overlap, smaller area


@pytest.fixture
async def districts(conn):
    ids = {}
    for key, code, wkt in (("A", "TN-CHN", A), ("B", "TN-CBE", B), ("C", "TN-MDU", C)):
        ids[key] = await conn.fetchval("SELECT district_id FROM administration.district WHERE district_code=$1", code)
        await conn.execute("UPDATE administration.district SET geometry=ST_GeomFromText($2,4326) WHERE district_id=$1", ids[key], wkt)
    yield ids
    await conn.execute("UPDATE administration.district SET geometry=NULL WHERE district_id = ANY($1)", list(ids.values()))


@pytest.fixture
async def hierarchy(conn, districts):
    """taluk + local body + ward inside district A."""
    a = districts["A"]
    t = await conn.fetchval("INSERT INTO administration.taluk (district_id,name,geometry) VALUES ($1,'T-Test',ST_GeomFromText($2,4326)) RETURNING taluk_id", a, box(80.0, 13.0, 80.3, 13.3))
    lb = await conn.fetchval("INSERT INTO administration.local_body (district_id,taluk_id,type,name,geometry) VALUES ($1,$2,'municipality','LB-Test',ST_GeomFromText($3,4326)) RETURNING local_body_id", a, t, box(80.0, 13.0, 80.2, 13.2))
    w = await conn.fetchval("INSERT INTO administration.ward (local_body_id,ward_number,geometry) VALUES ($1,'W1',ST_GeomFromText($2,4326)) RETURNING ward_id", lb, box(80.0, 13.0, 80.1, 13.1))
    yield a, t, lb, w
    await conn.execute("DELETE FROM complaints.complaint WHERE ward_id=$1 OR local_body_id=$2 OR taluk_id=$3", w, lb, t)
    await conn.execute("DELETE FROM administration.ward WHERE ward_id=$1", w)
    await conn.execute("DELETE FROM administration.local_body WHERE local_body_id=$1", lb)
    await conn.execute("DELETE FROM administration.taluk WHERE taluk_id=$1", t)


async def resolve(conn, lon, lat):
    return await conn.fetchrow("SELECT * FROM administration.resolve_jurisdiction($1,$2)", lon, lat)


# -- extension / DDL ---------------------------------------------------------------------
async def test_postgis_extension_and_geometry_columns(conn):
    assert await conn.fetchval("SELECT extversion FROM pg_extension WHERE extname='postgis'")
    cols = await conn.fetch("SELECT f_table_schema||'.'||f_table_name AS t, f_geometry_column AS c, srid, type "
                            "FROM geometry_columns WHERE f_table_schema IN ('administration','services','complaints')")
    got = {(r["t"], r["c"]): (r["srid"], r["type"]) for r in cols}
    for t in ("administration.district", "administration.taluk", "administration.block",
              "administration.local_body", "administration.ward", "administration.revenue_division"):
        assert got[(t, "geometry")] == (4326, "MULTIPOLYGON"), t
    assert got[("services.government_facility", "location")] == (4326, "POINT")
    assert got[("complaints.complaint", "location")] == (4326, "POINT")


async def test_gist_indexes_exist(conn):
    names = ["idx_district_geom", "idx_taluk_geom", "idx_block_geom", "idx_lb_geom", "idx_ward_geom",
             "idx_facility_geom", "idx_complaint_geom", "idx_facility_geog"]
    rows = await conn.fetch("SELECT indexname, indexdef FROM pg_indexes WHERE indexname = ANY($1)", names)
    assert {r["indexname"] for r in rows} == set(names)
    assert all("USING gist" in r["indexdef"] for r in rows)


async def test_srid_mismatch_is_rejected(conn):
    with pytest.raises(Exception, match="SRID"):
        await conn.execute("UPDATE administration.district SET geometry=ST_SetSRID(ST_GeomFromText($1),3857) WHERE district_code='TN-CHN'", A)


# -- resolve_jurisdiction -----------------------------------------------------------------
async def test_interior_point_resolves(conn, districts):
    assert (await resolve(conn, 80.45, 13.05))["district_id"] == districts["A"]
    assert (await resolve(conn, 80.75, 13.25))["district_id"] == districts["B"]


async def test_point_outside_every_polygon_resolves_to_nothing(conn, districts):
    assert (await resolve(conn, 78.0, 10.0))["district_id"] is None


async def test_boundary_and_vertex_points_are_resolved(conn, districts):
    """Regression (migration 005): ST_Contains dropped points exactly on a border/vertex."""
    edge = (await resolve(conn, 80.5, 13.25))["district_id"]
    assert edge in (districts["A"], districts["B"])          # on the A|B shared edge: one of them, not NULL
    assert (await resolve(conn, 80.0, 13.0))["district_id"] == districts["A"]    # vertex of A


async def test_overlap_resolves_deterministically_to_smallest_polygon(conn, districts):
    for _ in range(3):
        assert (await resolve(conn, 80.3, 13.3))["district_id"] == districts["C"]   # C is inside A, smaller
    assert (await resolve(conn, 80.1, 13.1))["district_id"] == districts["A"]


async def test_swapped_or_invalid_coordinates(conn, districts):
    assert (await resolve(conn, 13.25, 80.25))["district_id"] is None      # lon/lat swapped: valid range, outside area
    assert await resolve(conn, 200.0, 13.0) is None                       # out of range: no row at all
    assert await resolve(conn, 80.0, 95.0) is None


async def test_full_hierarchy_ward_local_body_taluk_district(conn, hierarchy):
    a, t, lb, w = hierarchy
    r = await resolve(conn, 80.05, 13.05)
    assert (r["ward_id"], r["local_body_id"], r["taluk_id"], r["district_id"]) == (w, lb, t, a)
    r = await resolve(conn, 80.15, 13.15)                                   # in local body + taluk, no ward
    assert (r["ward_id"], r["local_body_id"], r["taluk_id"]) == (None, lb, t)
    r = await resolve(conn, 80.25, 13.25)                                   # taluk only
    assert (r["local_body_id"], r["taluk_id"], r["district_id"]) == (None, t, a)


async def test_resolve_uses_spatial_index(conn, districts):
    await conn.execute("SET enable_seqscan = off")
    try:
        plan = "\n".join(r[0] for r in await conn.fetch(
            "EXPLAIN SELECT 1 FROM administration.district d WHERE ST_Covers(d.geometry, ST_SetSRID(ST_Point(80.1,13.1),4326))"))
    finally:
        await conn.execute("RESET enable_seqscan")
    assert "idx_district_geom" in plan, plan


# -- complaint location trigger -----------------------------------------------------------
async def _insert_complaint(conn, citizen_id, lat, lon):
    return await conn.fetchval(
        "INSERT INTO complaints.complaint (citizen_id,title,description,latitude,longitude) VALUES ($1,'t','d',$2,$3) RETURNING complaint_id",
        citizen_id, lat, lon)


async def test_trigger_fills_geometry_and_jurisdiction(conn, hierarchy, make_citizen):
    a, t, lb, w = hierarchy
    c = await make_citizen()
    cid = await _insert_complaint(conn, c["user"]["citizen_id"], 13.05, 80.05)
    row = await conn.fetchrow("SELECT ST_X(location) x, ST_Y(location) y, ST_SRID(location) srid, ward_id, local_body_id, taluk_id, district_id "
                              "FROM complaints.complaint WHERE complaint_id=$1", cid)
    assert (row["x"], row["y"], row["srid"]) == (80.05, 13.05, 4326)
    assert (row["ward_id"], row["local_body_id"], row["taluk_id"], row["district_id"]) == (w, lb, t, a)


async def test_trigger_keeps_explicit_jurisdiction_and_skips_null_coordinates(conn, districts, make_citizen):
    c = await make_citizen()
    none = await _insert_complaint(conn, c["user"]["citizen_id"], None, None)
    r = await conn.fetchrow("SELECT location, district_id FROM complaints.complaint WHERE complaint_id=$1", none)
    assert r["location"] is None and r["district_id"] is None
    explicit = await conn.fetchval(
        "INSERT INTO complaints.complaint (citizen_id,title,description,latitude,longitude,district_id) VALUES ($1,'t','d',13.05,80.05,$2) RETURNING complaint_id",
        c["user"]["citizen_id"], districts["B"])
    assert await conn.fetchval("SELECT district_id FROM complaints.complaint WHERE complaint_id=$1", explicit) == districts["B"]


async def test_trigger_fires_when_coordinates_are_updated(conn, districts, make_citizen):
    c = await make_citizen()
    cid = await _insert_complaint(conn, c["user"]["citizen_id"], None, None)
    await conn.execute("UPDATE complaints.complaint SET latitude=13.1, longitude=80.1 WHERE complaint_id=$1", cid)
    r = await conn.fetchrow("SELECT ST_X(location) x, district_id FROM complaints.complaint WHERE complaint_id=$1", cid)
    assert r["x"] == 80.1 and r["district_id"] == districts["A"]


# -- API ----------------------------------------------------------------------------------
async def test_resolve_jurisdiction_endpoint(client, hierarchy):
    a, t, lb, w = hierarchy
    r = await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": 13.05, "lon": 80.05})
    body = r.json()
    assert r.status_code == 200 and body["resolved_level"] == "ward" and body["ward_name"] == "W1"
    assert body["local_body_name"] == "LB-Test" and body["taluk_name"] == "T-Test" and body["district_name"] == "Chennai"
    assert (await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": 10.0, "lon": 78.0})).status_code == 404
    assert (await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": 95, "lon": 80})).status_code == 422
    assert (await client.get(f"{API}/gis/resolve-jurisdiction", params={"lat": "abc", "lon": 80})).status_code == 422


async def test_complaint_api_attributes_jurisdiction(client, conn, hierarchy, make_citizen):
    a, t, lb, w = hierarchy
    c = await make_citizen()
    r = await client.post(f"{API}/complaints", headers=c["headers"], json={
        "title": "Broken light", "description": "Street light broken near the park",
        "latitude": 13.05, "longitude": 80.05})
    assert r.status_code == 201, r.text
    row = await conn.fetchrow("SELECT ward_id, local_body_id, taluk_id, district_id, location IS NOT NULL AS g "
                              "FROM complaints.complaint WHERE complaint_ref=$1", r.json()["reference_number"])
    assert (row["ward_id"], row["local_body_id"], row["taluk_id"], row["district_id"], row["g"]) == (w, lb, t, a, True)


# -- facilities ---------------------------------------------------------------------------
def haversine_km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(d))


@pytest.fixture
async def facilities(conn):
    pts = (("Near PHC", 80.2707, 13.0827, "phc"), ("Tambaram PHC", 80.1270, 12.9249, "phc"),
           ("Distant PHC", 77.0, 11.0, "phc"), ("Near School", 80.2750, 13.0850, "school"))
    ids = []
    for name, lon, lat, typ in pts:
        ids.append(await conn.fetchval("INSERT INTO services.government_facility (name,facility_type,location) VALUES ($1,$4,ST_SetSRID(ST_MakePoint($2,$3),4326)) RETURNING facility_id", name, lon, lat, typ))
    yield
    await conn.execute("DELETE FROM services.government_facility WHERE facility_id = ANY($1)", ids)


async def test_nearby_facilities_order_filter_and_radius(client, facilities):
    q = {"lat": 13.0827, "lon": 80.2707, "radius_km": 50}
    names = [f["name"] for f in (await client.get(f"{API}/gis/facilities", params=q)).json()]
    assert names == ["Near PHC", "Near School", "Tambaram PHC"]                   # Distant PHC (~300 km) excluded
    only = [f["name"] for f in (await client.get(f"{API}/gis/facilities", params={**q, "facility_type": "school"})).json()]
    assert only == ["Near School"]
    tight = [f["name"] for f in (await client.get(f"{API}/gis/facilities", params={**q, "radius_km": 1})).json()]
    assert tight == ["Near PHC", "Near School"]
    assert (await client.get(f"{API}/gis/facilities", params={**q, "radius_km": 0})).status_code == 422


async def test_facility_distances_are_kilometres_and_accurate(client, facilities):
    res = (await client.get(f"{API}/gis/facilities", params={"lat": 13.0827, "lon": 80.2707, "radius_km": 50})).json()
    by = {f["name"]: f for f in res}
    expected = haversine_km(80.2707, 13.0827, 80.1270, 12.9249)
    assert expected == pytest.approx(by["Tambaram PHC"]["distance_km"], rel=0.01)    # sphere vs ellipsoid, <1%
    assert 20 < by["Tambaram PHC"]["distance_km"] < 24
    assert by["Near PHC"]["distance_km"] == pytest.approx(0, abs=0.001)
    assert (by["Near PHC"]["latitude"], by["Near PHC"]["longitude"]) == pytest.approx((13.0827, 80.2707))


async def test_facility_search_can_use_geography_index(conn, facilities):
    await conn.execute("SET enable_seqscan = off")
    try:
        plan = "\n".join(r[0] for r in await conn.fetch(
            "EXPLAIN SELECT 1 FROM services.government_facility f WHERE ST_DWithin(f.location::geography, "
            "ST_SetSRID(ST_MakePoint(80.27,13.08),4326)::geography, 5000)"))
    finally:
        await conn.execute("RESET enable_seqscan")
    assert "idx_facility_geog" in plan, plan
