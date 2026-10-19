-- =====================================================================
-- Migration 005 (REQUIRES PostGIS): spatial correctness fixes found by testing on real PostGIS.
--
--  1. resolve_jurisdiction used ST_Contains, which EXCLUDES the polygon boundary: a point exactly
--     on a district/taluk border or vertex resolved to nothing. Now ST_Covers.
--  2. Overlapping polygons gave an arbitrary (physical-order) answer. Now the smallest covering
--     polygon wins, ties broken by id, so the result is deterministic.
--  3. Out-of-range coordinates return no row instead of a meaningless point.
--  4. The nearby-facility query casts location::geography, which cannot use the geometry GIST
--     index (it seq-scanned). Adds a matching expression index on (location::geography).
--
-- Idempotent. Skipped by the stub (no-PostGIS) test mode, which has no spatial functions.
-- =====================================================================
CREATE OR REPLACE FUNCTION administration.resolve_jurisdiction(p_lon double precision, p_lat double precision)
RETURNS TABLE (ward_id int, local_body_id int, taluk_id int, district_id int) AS $$
  WITH pt AS (
    SELECT ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326) AS g
    WHERE p_lon BETWEEN -180 AND 180 AND p_lat BETWEEN -90 AND 90
  )
  SELECT w.ward_id,
         COALESCE(w.local_body_id, lb.local_body_id),
         COALESCE(lb.taluk_id, t.taluk_id),
         COALESCE(t.district_id, lb.district_id, d.district_id)
  FROM pt
  LEFT JOIN LATERAL (
      SELECT x.ward_id, x.local_body_id FROM administration.ward x
      WHERE ST_Covers(x.geometry, pt.g) ORDER BY ST_Area(x.geometry), x.ward_id LIMIT 1) w ON true
  LEFT JOIN LATERAL (
      SELECT x.local_body_id, x.taluk_id, x.district_id FROM administration.local_body x
      WHERE ST_Covers(x.geometry, pt.g) ORDER BY ST_Area(x.geometry), x.local_body_id LIMIT 1) lb ON true
  LEFT JOIN LATERAL (
      SELECT x.taluk_id, x.district_id FROM administration.taluk x
      WHERE ST_Covers(x.geometry, pt.g) ORDER BY ST_Area(x.geometry), x.taluk_id LIMIT 1) t ON true
  LEFT JOIN LATERAL (
      SELECT x.district_id FROM administration.district x
      WHERE ST_Covers(x.geometry, pt.g) ORDER BY ST_Area(x.geometry), x.district_id LIMIT 1) d ON true;
$$ LANGUAGE sql STABLE;

CREATE INDEX IF NOT EXISTS idx_facility_geog
  ON services.government_facility USING GIST ((location::geography));
