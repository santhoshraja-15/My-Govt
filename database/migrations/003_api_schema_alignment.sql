-- =====================================================================
-- Migration 003: columns the API/UI already rely on but 001_schema.sql lacked.
--   * complaints.complaint.address        (ComplaintCreate.address, shown on the tracking page)
--   * identity.citizen_profile attributes (education_level / marital_status / family_size are
--     eligibility-rule attributes accepted by EligibilityRequest and CitizenProfileIn)
-- Idempotent. Consent is NOT stored here: it lives in identity.consent.
-- =====================================================================
ALTER TABLE complaints.complaint ADD COLUMN IF NOT EXISTS address text;

ALTER TABLE identity.citizen_profile
  ADD COLUMN IF NOT EXISTS education_level text,
  ADD COLUMN IF NOT EXISTS marital_status  text,
  ADD COLUMN IF NOT EXISTS family_size     int CHECK (family_size IS NULL OR family_size >= 1);
