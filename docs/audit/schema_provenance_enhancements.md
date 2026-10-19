# Database Schema Provenance Enhancements

## Overview
To provide end-to-end data traceability from official Tamil Nadu government gazettes down to individual AI retrieval decisions, migration `002_provenance_and_audit_fixes.sql` introduces foundational provenance and governance columns.

## Schema Modifications in Migration 002

### 1. `administration.state`
- `state_name_ta text`: Native Tamil state name (`தமிழ்நாடு`).

### 2. `administration.district`
- `headquarters text`: District administrative headquarters city.
- `lgd_code int UNIQUE`: Local Government Directory (MoPR) standard identifier.
- `census_code int`: Census of India standard district code.
- `verification_status text`: Governance verification status (`official_verified`, `externally_referenced`, `provisional`, `unverified`, `deprecated`).

### 3. `administration.department`
- `short_name text`: Standard administrative abbreviation (e.g. `Revenue`, `RDPR`, `Health`).
- `verified_at timestamptz`: Timestamp of last source audit.
- `verified_by text`: Auditor or authority reference.
- `source_document_ref text`: Government Order or official gazette reference.
- `verification_status text`: Official verification lifecycle status.

### 4. `schemes.scheme`
- `verified_by text`: Verification officer or audit agency.
- `source_document_ref text`: Relevant Government Order (e.g. `GO Ms No 1 Social Welfare 2023`).
- `funding_pattern text`: `100% State`, `100% Central`, `Centrally Sponsored (60:40)`, `Centrally Sponsored (50:50)`.
- `verification_status text`: Data verification status.

### 5. `services.service`
- `tnega_service_id text`: Official TNeGA portal service code.
- `statutory_act_ref text`: Governing Tamil Nadu act or rule.
- `verification_status text`: Verification status.
- `verified_by text`: Authority auditor.

### 6. `complaints.sla_rule`
- `is_statutory boolean`: Distinguishes statutory Citizen Charter mandates from internal platform benchmarks.
- `sla_source_type text`: `statutory_charter`, `departmental_order`, `operational_target`, or `provisional`.
- `notes text`: Operational guidance and context.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
