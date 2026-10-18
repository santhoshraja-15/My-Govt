-- =====================================================================
-- Migration 004: verification governance
--   * system.verification_status_log  - every status change (old, new, reason, timestamp)
--   * trigger  - logs changes automatically; blocks leaving 'deprecated'
--   * CHECK    - 'official_verified' requires a non-empty source_document_ref
--   * administration.district.source_document_ref (districts had no provenance column)
--   * district/department default status 'provisional' (was 'official_verified')
--
-- Constraints are added NOT VALID so existing databases can be migrated; the seed demotes
-- unsupported rows and then VALIDATEs them (seeds/002_verified_seed_data.sql, section 11).
-- Idempotent.
-- =====================================================================
ALTER TABLE administration.district ADD COLUMN IF NOT EXISTS source_document_ref text;

-- Migration 002 defaulted these two to 'official_verified', so any new row silently claimed
-- verification. New rows must start provisional.
ALTER TABLE administration.district   ALTER COLUMN verification_status SET DEFAULT 'provisional';
ALTER TABLE administration.department ALTER COLUMN verification_status SET DEFAULT 'provisional';

CREATE TABLE IF NOT EXISTS system.verification_status_log (
  log_id      bigserial PRIMARY KEY,
  table_name  text NOT NULL,                 -- e.g. schemes.scheme
  record_key  text NOT NULL,                 -- natural key (scheme_code, district_code, ...)
  old_status  text,
  new_status  text NOT NULL,
  reason      text NOT NULL,
  changed_by  text NOT NULL DEFAULT current_user,
  changed_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vlog_record ON system.verification_status_log (table_name, record_key, changed_at);

-- TG_ARGV[0] = natural-key column. The reason comes from the session setting
-- app.verification_reason (set_config) and is mandatory.
CREATE OR REPLACE FUNCTION system.log_verification_change() RETURNS trigger AS $$
DECLARE
  v_reason text := nullif(current_setting('app.verification_reason', true), '');
  v_key    text := to_jsonb(NEW) ->> TG_ARGV[0];
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.verification_status IS NOT DISTINCT FROM NEW.verification_status THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.verification_status = 'deprecated' THEN
    RAISE EXCEPTION 'verification_status of % % is deprecated and cannot change', TG_TABLE_NAME, v_key;
  END IF;
  INSERT INTO system.verification_status_log (table_name, record_key, old_status, new_status, reason)
  VALUES (TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, v_key,
          CASE WHEN TG_OP = 'UPDATE' THEN OLD.verification_status END,
          NEW.verification_status,
          coalesce(v_reason, 'no reason supplied'));
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DO $$
DECLARE
  t record;
BEGIN
  FOR t IN SELECT * FROM (VALUES
      ('administration', 'district',           'district_code'),
      ('administration', 'department',         'department_code'),
      ('schemes',        'scheme',             'scheme_code'),
      ('services',       'service',            'service_code'),
      ('complaints',     'complaint_category', 'category_code')
  ) AS v(s, tbl, keycol)
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_verification_log ON %I.%I', t.s, t.tbl);
    EXECUTE format(
      'CREATE TRIGGER trg_verification_log AFTER INSERT OR UPDATE OF verification_status ON %I.%I '
      'FOR EACH ROW EXECUTE FUNCTION system.log_verification_change(%L)', t.s, t.tbl, t.keycol);

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'chk_' || t.tbl || '_verified_has_source'
                     AND conrelid = format('%I.%I', t.s, t.tbl)::regclass) THEN
      EXECUTE format(
        'ALTER TABLE %I.%I ADD CONSTRAINT %I CHECK '
        '(verification_status <> ''official_verified'' OR btrim(coalesce(source_document_ref, '''')) <> '''') NOT VALID',
        t.s, t.tbl, 'chk_' || t.tbl || '_verified_has_source');
    END IF;
  END LOOP;
END $$;
