-- =====================================================================
-- Migration 006: routing/authority provenance
-- administration.authority and complaints.routing_rule had no provenance, and no authority or
-- routing rule was seeded, so complaints never received an authority. These columns mark routing
-- data as provisional so it is never presented as an officially verified office.
-- Idempotent.
-- =====================================================================
ALTER TABLE administration.authority
  ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'provisional'
    CHECK (verification_status IN ('official_verified','externally_referenced','provisional','unverified','deprecated')),
  ADD COLUMN IF NOT EXISTS is_routing_placeholder boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS notes text;

ALTER TABLE complaints.routing_rule
  ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'provisional'
    CHECK (verification_status IN ('official_verified','externally_referenced','provisional','unverified','deprecated'));

COMMENT ON COLUMN administration.authority.is_routing_placeholder IS
  'TRUE = a department-level routing target created by the platform, NOT a verified government office or officer.';

-- one routing placeholder per (department, level) and one rule per (category, level)
CREATE UNIQUE INDEX IF NOT EXISTS uq_authority_placeholder
  ON administration.authority (department_id, jurisdiction_level) WHERE is_routing_placeholder;
CREATE UNIQUE INDEX IF NOT EXISTS uq_routing_rule_category_level
  ON complaints.routing_rule (category_id, jurisdiction_level, priority_order);
