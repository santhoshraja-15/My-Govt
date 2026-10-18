-- =====================================================================
-- Migration 002: Provenance Tracking & Audit Alignment Fixes
-- Enhances administrative, schemes, services, and complaints schemas
-- with official verification status, LGD codes, Tamil nomenclature,
-- and source documentation references.
-- =====================================================================

-- 1. State Table Enhancements
ALTER TABLE administration.state
  ADD COLUMN IF NOT EXISTS state_name_ta text;

-- 2. District Table Enhancements (LGD, Census, Headquarters)
ALTER TABLE administration.district
  ADD COLUMN IF NOT EXISTS headquarters text,
  ADD COLUMN IF NOT EXISTS lgd_code int UNIQUE,
  ADD COLUMN IF NOT EXISTS census_code int,
  ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'official_verified'
    CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated'));

-- 3. Department Table Enhancements (Short Name, Verification Provenance)
ALTER TABLE administration.department
  ADD COLUMN IF NOT EXISTS short_name text,
  ADD COLUMN IF NOT EXISTS verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS verified_by text,
  ADD COLUMN IF NOT EXISTS source_document_ref text,
  ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'official_verified'
    CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated'));

-- 4. Schemes Table Enhancements (Provenance, Co-funding, Verified Authority)
ALTER TABLE schemes.scheme
  ADD COLUMN IF NOT EXISTS verified_by text,
  ADD COLUMN IF NOT EXISTS source_document_ref text,
  ADD COLUMN IF NOT EXISTS funding_pattern text DEFAULT '100% State'
    CHECK (funding_pattern IN ('100% State', '100% Central', 'Centrally Sponsored (60:40)', 'Centrally Sponsored (50:50)', 'Other')),
  ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'provisional'
    CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated'));

-- 5. Services Table Enhancements (e-Sevai Portal Mapping, Provenance)
ALTER TABLE services.service
  ADD COLUMN IF NOT EXISTS verified_by text,
  ADD COLUMN IF NOT EXISTS source_document_ref text,
  ADD COLUMN IF NOT EXISTS tnega_service_id text,
  ADD COLUMN IF NOT EXISTS statutory_act_ref text,
  ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'provisional'
    CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated'));

-- 6. Complaint Categories & SLA Rules Provenance
ALTER TABLE complaints.complaint_category
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS verification_status text DEFAULT 'provisional'
    CHECK (verification_status IN ('official_verified', 'externally_referenced', 'provisional', 'unverified', 'deprecated')),
  ADD COLUMN IF NOT EXISTS source_document_ref text;

ALTER TABLE complaints.sla_rule
  ADD COLUMN IF NOT EXISTS is_statutory boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS sla_source_type text NOT NULL DEFAULT 'operational_target'
    CHECK (sla_source_type IN ('statutory_charter', 'departmental_order', 'operational_target', 'provisional')),
  ADD COLUMN IF NOT EXISTS notes text;

COMMENT ON COLUMN complaints.sla_rule.sla_source_type IS 'Distinguishes between legally enforceable Citizen Charter SLAs and platform operational performance targets.';
COMMENT ON COLUMN schemes.scheme.verification_status IS 'Data governance verification lifecycle status.';
