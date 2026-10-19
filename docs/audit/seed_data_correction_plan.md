# Seed Data Correction & Execution Plan

## Objectives
1. Eliminate all syntax errors and constraint violations present in `001_seed_data.sql`.
2. Deploy `002_provenance_and_audit_fixes.sql` migration to equip the database with provenance tracking.
3. Provide `002_verified_seed_data.sql` as the verified, audited seed dataset containing correct Tamil Nadu data.
4. Establish automated verification scripts in `scripts/` to prevent regression.

## Execution Steps
1. **Discovery & Verification (`scripts/discovery/`)**:
   - Probe official portals and catalog status, latency, and certificates.
2. **Programmatic Comparison (`scripts/comparison/`)**:
   - Audit seed data for duplicates, typos, and schema misalignment.
3. **Database Migration (`database/migrations/002_provenance_and_audit_fixes.sql`)**:
   - Apply provenance columns and constraints.
4. **Verified Seed Generation (`database/seeds/002_verified_seed_data.sql`)**:
   - Insert 38 deduplicated districts, 15 verified departments, 10 complaint categories with integer keys and unique codes, 30 schemes with explicit funding patterns, and 20 e-Sevai services.
5. **Raw Dataset Archival (`data/raw/official/`)**:
   - Ingest immutable JSON datasets with SHA-256 metadata.
6. **Documentation & Reporting (`docs/audit/`)**:
   - Publish 9 comprehensive audit reports.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
