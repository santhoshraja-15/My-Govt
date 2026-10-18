# MyGovt Audit Compliance Matrix

| Requirement / Constraint | Audit Finding | Remediation Action | Compliance State |
|---|---|---|---|
| **Dedicated Audit Branch** | Working on `audit/tn-data-verification` | Branch created; changes isolated from main | **COMPLIANT** |
| **Official Tamil Nadu Sources Only** | Examined tn.gov.in, tnega.tn.gov.in, tn.data.gov.in, esevai.tn.gov.in | Sources cataloged in `sources_catalog.json` | **COMPLIANT** |
| **No Central Data as TN State Substitute** | PM-Kisan was seeded as TN State scheme | Reclassified to `scheme_level = 'central'`, funding `100% Central` | **COMPLIANT** |
| **No Fabricated URLs or Verification** | All probes executed live; actual probe logs recorded | Unreachable/timed-out URLs documented truthfully | **COMPLIANT** |
| **Immutable Raw Data with Provenance** | Previously empty raw directories | Ingested raw JSON files with SHA-256 `.meta.json` files | **COMPLIANT** |
| **District Deduplication & Accuracy** | 4 duplicate codes + 'Thane' Maharashtra typo found | All 38 codes uniquely standardized; Thane -> Thanjavur | **COMPLIANT** |
| **Schema Alignment** | 7 column & check constraint mismatches | Fixed in migration 002 and verified seed 002 | **COMPLIANT** |
| **SLA Integrity** | Seed SLAs presented without source distinction | Added `sla_source_type = 'operational_target'`, documented | **COMPLIANT** |
| **9 Audit Documents in `docs/audit/`** | 9 markdown reports requested | All 9 generated with comprehensive analysis | **COMPLIANT** |

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
