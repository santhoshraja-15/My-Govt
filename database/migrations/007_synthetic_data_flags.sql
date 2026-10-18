-- =====================================================================
-- Migration 007: explicit labelling of synthetic (generated) records
-- Synthetic citizens/complaints exist only for development and load testing and must never be
-- mistaken for real people or official data. is_synthetic is set only by backend/scripts/synth_data.py.
-- Synthetic app_users must use the reserved, undeliverable domain @synthetic.invalid (RFC 2606),
-- which the registration API's email validator also rejects, so a real user can never collide.
-- Idempotent.
-- =====================================================================
ALTER TABLE identity.app_user  ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false;
ALTER TABLE identity.citizen   ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false,
                               ADD COLUMN IF NOT EXISTS synthetic_batch text;
ALTER TABLE complaints.complaint ADD COLUMN IF NOT EXISTS is_synthetic boolean NOT NULL DEFAULT false,
                                 ADD COLUMN IF NOT EXISTS synthetic_batch text;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_app_user_synthetic_email') THEN
    ALTER TABLE identity.app_user ADD CONSTRAINT chk_app_user_synthetic_email
      CHECK (NOT is_synthetic OR email LIKE '%@synthetic.invalid');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_citizen_synthetic_batch') THEN
    ALTER TABLE identity.citizen ADD CONSTRAINT chk_citizen_synthetic_batch
      CHECK (NOT is_synthetic OR synthetic_batch IS NOT NULL);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_complaint_synthetic_batch') THEN
    ALTER TABLE complaints.complaint ADD CONSTRAINT chk_complaint_synthetic_batch
      CHECK (NOT is_synthetic OR synthetic_batch IS NOT NULL);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_complaint_synthetic ON complaints.complaint (synthetic_batch) WHERE is_synthetic;
CREATE INDEX IF NOT EXISTS idx_citizen_synthetic   ON identity.citizen (synthetic_batch)   WHERE is_synthetic;
