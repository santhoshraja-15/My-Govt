# Verification Gap Analysis

## Summary of Findings
Programmatic audit executed across all seed records identified **10 distinct discrepancies**, categorized by severity:
- **CRITICAL**: 1 (Would cause database runtime exceptions or severe factual corruption)
- **HIGH**: 5 (Schema column mismatch preventing execution)
- **MEDIUM**: 3 (Jurisdiction and provenance classification gaps)
- **LOW**: 1 (Operational documentation clarification)

## Detailed Gap Inventory
### 1. [HIGH] SCHEMA_COLUMN_MISMATCH
- **Target Table**: `administration.state`
- **Field / Record**: `state_name_ta` (Global)
- **Description**: Seed inserts into column 'state_name_ta', but schema defines only (state_id, state_code, state_name). Column does not exist in 001_schema.sql.
- **Remediation**: Add 'state_name_ta text' to administration.state in schema migration, or omit from insert.

### 2. [HIGH] SCHEMA_COLUMN_MISMATCH
- **Target Table**: `administration.district`
- **Field / Record**: `district_name_ta, headquarters` (Global)
- **Description**: Seed inserts 'district_name_ta' and 'headquarters', but schema defines columns as 'name_ta' and lacks 'headquarters'.
- **Remediation**: Align column names to 'name_ta' and add 'headquarters text' to schema migration.

### 3. [HIGH] SCHEMA_COLUMN_MISMATCH
- **Target Table**: `administration.department`
- **Field / Record**: `department_name_ta, short_name, portal_url` (Global)
- **Description**: Seed inserts 'department_name_ta', 'short_name', and 'portal_url', whereas schema defines 'name_ta', 'website_url', and lacks 'short_name'.
- **Remediation**: Align columns to schema or add missing columns in schema migration.

### 4. [HIGH] SCHEMA_COLUMN_MISMATCH
- **Target Table**: `schemes.scheme`
- **Field / Record**: `name, description, official_source_url` (Global)
- **Description**: Seed inserts columns (name, description, official_source_url), but schema expects (scheme_name, short_description/full_description, official_url).
- **Remediation**: Update seed statement column mapping to match schema.

### 5. [HIGH] SCHEMA_COLUMN_MISMATCH
- **Target Table**: `services.service`
- **Field / Record**: `name, processing_days, official_source_url` (Global)
- **Description**: Seed inserts columns (name, processing_days, official_source_url), but schema expects (service_name, processing_time, official_url).
- **Remediation**: Update seed statement column mapping to match schema.

### 6. [CRITICAL] SCHEMA_TYPE_MISMATCH
- **Target Table**: `complaints.complaint_category`
- **Field / Record**: `category_id, category_code` (Global)
- **Description**: Seed inserts UUIDs into category_id (which is serial INT in schema) and omits category_code (which is UNIQUE NOT NULL in schema).
- **Remediation**: Use integer category_id or omit to let serial sequence generate, provide category_code, and align column names.

### 7. [MEDIUM] SCHEME_JURISDICTION_MISCLASSIFICATION
- **Target Table**: `schemes.scheme`
- **Field / Record**: `scheme_level` (TN-PM-KISAN)
- **Description**: PM-Kisan (Pradhan Mantri Kisan Samman Nidhi) is a 100% centrally-sponsored Central Sector Scheme, but is seeded as scheme_level='state'.
- **Remediation**: Update scheme_level='central' and add notes explaining Tamil Nadu state administration via Commissionerate of Agriculture.

### 8. [MEDIUM] SCHEME_JURISDICTION_MISCLASSIFICATION
- **Target Table**: `schemes.scheme`
- **Field / Record**: `scheme_name / category` (TN-NIRP-PENSION)
- **Description**: IGNOAPS is a National Social Assistance Programme (NSAP) component co-funded by Central & State governments.
- **Remediation**: Add co-funding provenance (Central NSAP + State Social Welfare top-up).

### 9. [MEDIUM] SYNTHETIC_DATASET_METRICS
- **Target Table**: `system.dataset_registry`
- **Field / Record**: `quality_completeness, validation_status` (Global)
- **Description**: Dataset registry contains claims of 1.0/0.95 quality scores with 'loaded' status for GeoJSON boundaries, but no raw GeoJSON files were ever downloaded or stored in data/raw/.
- **Remediation**: Set quality scores to actual validated metrics, set processing_status to 'raw' or 'pending' until actual boundary GeoJSON is ingested.

### 10. [LOW] APPLICATION_DEFINED_TARGETS
- **Target Table**: `complaints.sla_rule`
- **Field / Record**: `resolution_hours, escalation_hours` (Global)
- **Description**: SLA rules (24h/12h for high, 72h/48h for medium) are prototype application targets and not statutory citizen charter SLA mandates.
- **Remediation**: Document clearly in audit and catalog that these are platform operational defaults, pending integration with CM Helpline 1100 departmental SLAs.


## Resolution Status
All identified gaps have been resolved through:
1. `database/migrations/002_provenance_and_audit_fixes.sql` (schema alignment and provenance tracking fields).
2. `database/seeds/002_verified_seed_data.sql` (error-free, deduplicated, verified seed insertion).
3. Raw data checksums and metadata tracking in `data/raw/official/`.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
