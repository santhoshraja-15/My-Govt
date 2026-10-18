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
