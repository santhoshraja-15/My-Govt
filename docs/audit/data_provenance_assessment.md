# Data Provenance & Lineage Assessment

## Principle of Immutability
All external government datasets ingested into MyGovt follow strict append-only and immutable raw storage principles:
1. **Immutable Ingestion**: Raw JSON, CSV, and GeoJSON files downloaded from official endpoints are written directly to `data/raw/official/` and never mutated in place.
2. **Cryptographic Checksums**: Every raw file is paired with an adjacent `.meta.json` containing its SHA-256 digest, byte count, fetch timestamp, and verified source URL.
3. **Database Provenance Foreign Keys**: All operational tables (`schemes.scheme`, `services.service`, `administration.department`, `administration.district`) link back to `system.source_registry(source_id)` and `system.dataset_registry(dataset_id)`.

## Raw Dataset Integrity Register
| Dataset File | File Format | SHA-256 Digest (Prefix) | Record Count | Processing Status | Validation Status |
|---|---|---|---|---|---|
| `tn_districts_master_2026.json` | JSON | `68ad7e00adeef9c2...` | 38 | `validated` | `official_verified` |
| `tn_schemes_verified_2026.json` | JSON | `5dccdfdb61db6e6c...` | 12 | `validated` | `official_verified` |
| `tnega_esevai_services_2026.json` | JSON | `908ed80047c35344...` | 10 | `validated` | `official_verified` |
| `sources_probe_results.json` | JSON | Active Probe Results | 15 | `validated` | `official_verified` |

## Synthetic Dataset Metrics Remediation
In the original seed data (`001_seed_data.sql`), `system.dataset_registry` contained synthetic entries claiming 100% completeness and accuracy for administrative boundaries (`Tamil Nadu Administrative Boundaries 2024`) with status `loaded`, despite zero boundary files existing on disk.
This audit has remediated those claims:
- Genuine SHA-256 checksums have been calculated from actual raw JSON files on disk.
- Synthetic perfection claims were replaced with auditable metrics grounded in real downloaded data.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*

---

## Update 2026-10-19 — what is and is not established

**File integrity is not data authenticity.** The SHA-256 values recorded in `system.dataset_registry` match the JSON files on
disk (checked by `scripts.seed` and by a CI job), which only proves the files were not altered after they were hashed.

| Question | Finding |
|---|---|
| Is any record `official_verified`? | **No.** No official order text was located for any record (see below). The database now enforces `official_verified ⇒ source_document_ref` and logs every status change with a reason (`system.verification_status_log`). |
| Districts / LGD codes | 38 districts, 38 unique LGD codes – **but the codes come from the curated JSON and were not checked against the LGD directory**. The earlier "Tiruvannamalai 583" correction is therefore also unverified. |
| Departments | names and URLs unchecked; the official department list page returned only a redirect stub. |
| Schemes | 11 carry a dataset-asserted GO/guideline text (retained for follow-up only); none could be located; the Breakfast Scheme's department may be Social Welfare rather than School Education (search result, unconfirmed). PM-Kisan is correctly `externally_referenced`. |
| Services / fees | the official e-Sevai page lists **119 services** and says fees apply "if any" without amounts; the seed's 10 services, uniform ₹60 charge, "Free" government fees and processing times have **no supporting evidence**. The UI now shows them as *unconfirmed* and the API returns `charges_verified: false`. |
| SLA targets | platform operational targets, not statutory charters. |
| Ingested documents | 4 real PDFs fetched from tn.gov.in (forms, not orders); recorded with URL, retrieval time and SHA-256, status `unverified`. One (Tamil anthem) uses a legacy font and is flagged unreadable. |

**Dependencies for closing these gaps:** a reviewer with access to the Government Orders / department pages, the LGD directory,
and the e-Sevai service list. Promotion path: add `source_document_ref` and evidence in a reviewed change to seed section 11
(`database/seeds/002_verified_seed_data.sql`) with a reason; the log records it. Full register:
[verification_decisions_2026-10-18.csv](verification_decisions_2026-10-18.csv).
