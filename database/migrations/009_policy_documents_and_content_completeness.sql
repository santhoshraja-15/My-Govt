-- =====================================================================
-- Migration 009: policy-document catalogue + scheme/service content completeness
--   * documents.policy_document  - catalogue of official Tamil Nadu government documents (G.O.s, policies, circulars,
--                                  notifications, Acts) with identifiers, Tamil/English summaries and verified PDF links.
--                                  Separate from documents.document, which holds ingested full text and embeddings.
--   * schemes.scheme  - eligibility / exclusions / application steps / source evidence columns
--   * services.service - eligibility / application steps / forms / source evidence columns
--   * every new verification_status is governed like the other tables: logged by trigger, and 'official_verified'
--     requires a non-empty source_document_ref.
-- Idempotent. Forward-only.
-- =====================================================================

CREATE TABLE IF NOT EXISTS documents.policy_document (
  policy_document_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_code             text NOT NULL UNIQUE,                   -- stable id, e.g. DOC-NOT-GAZ-2026-436
  category             text NOT NULL CHECK (category IN ('government_order', 'policy', 'circular', 'notification', 'act')),
  identifier           text,                                   -- G.O. / R.O.C. / notification / Act number as published
  title                text NOT NULL,
  title_ta             text,                                   -- only when the issuer published a Tamil title
  issuing_authority    text NOT NULL,
  department_id        integer REFERENCES administration.department(department_id),
  issued_on            date,                                   -- actual issue / publication date; NULL if not confirmed
  effective_on         date,
  summary_en           text NOT NULL,
  summary_ta           text,
  summary_ta_reviewed  boolean NOT NULL DEFAULT false,         -- Tamil summaries are unreviewed translations unless true
  language             text NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'ta', 'bilingual')),
  related_topics       text[] NOT NULL DEFAULT '{}',
  source_page_url      text NOT NULL,                          -- official listing / landing page
  pdf_url              text,                                   -- direct official PDF; NULL when none is confirmed
  pdf_sha256           text,
  pdf_pages            integer,
  legal_status         text,                                   -- e.g. 'published in Extraordinary Gazette'; NULL when unknown
  superseded_status    text NOT NULL DEFAULT 'unknown' CHECK (superseded_status IN ('unknown', 'in_force', 'superseded', 'repealed')),
  verification_status  text NOT NULL DEFAULT 'provisional'
                         CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated')),
  source_document_ref  text,
  verification_method  text,
  last_checked_on      date,
  notes                text,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_policy_document_verified_has_source
    CHECK (verification_status <> 'official_verified' OR btrim(coalesce(source_document_ref, '')) <> '')
);
CREATE INDEX IF NOT EXISTS idx_policy_document_cat_date ON documents.policy_document (category, issued_on DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_policy_document_authority ON documents.policy_document (issuing_authority);
CREATE INDEX IF NOT EXISTS idx_policy_document_trgm ON documents.policy_document
  USING gin ((coalesce(title, '') || ' ' || coalesce(title_ta, '') || ' ' || coalesce(identifier, '') || ' ' || coalesce(summary_en, '') || ' ' || coalesce(summary_ta, '')) gin_trgm_ops);

DROP TRIGGER IF EXISTS trg_policy_document_updated ON documents.policy_document;
CREATE TRIGGER trg_policy_document_updated BEFORE UPDATE ON documents.policy_document
  FOR EACH ROW EXECUTE FUNCTION system.touch_updated_at();
DROP TRIGGER IF EXISTS trg_verification_log ON documents.policy_document;
CREATE TRIGGER trg_verification_log AFTER INSERT OR UPDATE OF verification_status ON documents.policy_document
  FOR EACH ROW EXECUTE FUNCTION system.log_verification_change('doc_code');

-- ── schemes: eligibility, exclusions, application procedure and evidence ─────────────────────────────
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS implementing_department text;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS purpose text;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS target_beneficiaries text;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS eligibility_points jsonb NOT NULL DEFAULT '[]';   -- ["text", ...]
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS exclusion_points jsonb NOT NULL DEFAULT '[]';
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS application_steps jsonb NOT NULL DEFAULT '[]';
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS how_to_apply_note text;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS source_urls jsonb NOT NULL DEFAULT '[]';           -- [{"url":..,"label":..}]
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS last_checked_on date;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS content_notes text;                                -- what is uncertain / historical
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS field_evidence jsonb NOT NULL DEFAULT '{}';        -- {"field": {"url","checked_on","confirmed"}}
ALTER TABLE schemes.document_requirement ADD COLUMN IF NOT EXISTS requirement_level text;
ALTER TABLE schemes.benefit ADD COLUMN IF NOT EXISTS amount_status text;

-- ── services: eligibility, procedure, forms and evidence ─────────────────────────────────────────────
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS responsible_department text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS eligibility_points jsonb NOT NULL DEFAULT '[]';
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS application_steps jsonb NOT NULL DEFAULT '[]';
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS how_to_apply text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS applicable_rules text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS forms jsonb NOT NULL DEFAULT '[]';
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS source_urls jsonb NOT NULL DEFAULT '[]';
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS last_checked_on date;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS content_notes text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS fee_note text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS processing_time_note text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS field_evidence jsonb NOT NULL DEFAULT '{}';
ALTER TABLE services.service_requirement ADD COLUMN IF NOT EXISTS requirement_level text;
ALTER TABLE schemes.scheme ADD COLUMN IF NOT EXISTS short_description_ta text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS description_ta text;
ALTER TABLE services.service ADD COLUMN IF NOT EXISTS fee_status text;

-- Constraints are (re)created by name so a database that applied an earlier draft of this migration gets the final value lists.
ALTER TABLE schemes.document_requirement DROP CONSTRAINT IF EXISTS document_requirement_requirement_level_check;
ALTER TABLE schemes.document_requirement ADD CONSTRAINT document_requirement_requirement_level_check
  CHECK (requirement_level IN ('required', 'conditional', 'category_specific', 'recommended', 'unverified'));
ALTER TABLE services.service_requirement DROP CONSTRAINT IF EXISTS service_requirement_requirement_level_check;
ALTER TABLE services.service_requirement ADD CONSTRAINT service_requirement_requirement_level_check
  CHECK (requirement_level IN ('required', 'conditional', 'category_specific', 'recommended', 'unverified'));
ALTER TABLE schemes.benefit DROP CONSTRAINT IF EXISTS benefit_amount_status_check;
ALTER TABLE schemes.benefit ADD CONSTRAINT benefit_amount_status_check
  CHECK (amount_status IN ('verified_current', 'historical', 'unverified', 'varies', 'not_applicable'));
ALTER TABLE services.service DROP CONSTRAINT IF EXISTS service_fee_status_check;
ALTER TABLE services.service ADD CONSTRAINT service_fee_status_check
  CHECK (fee_status IN ('listed_official_2023', 'unverified', 'not_listed'));
