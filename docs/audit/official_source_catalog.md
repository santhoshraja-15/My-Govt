# Official Tamil Nadu Government Source Catalog

## Catalog Summary
This catalog documents verified official government domains, API gateways, and data repositories serving Tamil Nadu governance data. Probed on 2026-10-18 05:20:35 UTC.

## Probed Endpoints & Live Verification Status
| Source Code | Organization / Portal Name | Official URL | Jurisdiction | Status | HTTP Code | Latency | Classification |
|---|---|---|---|---|---|---|---|
| `TN_GOV_PORTAL` | Tamil Nadu Government State Portal | [https://www.tn.gov.in](https://www.tn.gov.in) | State | **ACCESSIBLE** | 200 | 518ms | `official` |
| `TN_TNEGA` | Tamil Nadu e-Governance Agency (TNeGA) | [https://tnega.tn.gov.in](https://tnega.tn.gov.in) | State | **ACCESSIBLE** | 200 | 331ms | `official` |
| `TN_OPEN_DATA` | Tamil Nadu Open Data Portal | [https://tn.data.gov.in](https://tn.data.gov.in) | State | **ACCESSIBLE** | 200 | 834ms | `official` |
| `TN_DISTRICTS_NIC` | Tamil Nadu District Portals (NIC) | [https://tndistricts.nic.in](https://tndistricts.nic.in) | State | **NETWORK_ERROR** | None | 12140ms | `official` |
| `TN_ESEVAI` | Tamil Nadu e-Sevai Portal | [https://www.esevai.tn.gov.in](https://www.esevai.tn.gov.in) | State | **NETWORK_ERROR** | None | 12148ms | `official` |
| `TN_RDPR` | Rural Development and Panchayat Raj Department | [https://tnrd.tn.gov.in](https://tnrd.tn.gov.in) | State | **ACCESSIBLE** | 200 | 356ms | `official` |
| `TN_WELFARE` | Social Welfare and Women Empowerment Department | [https://www.socialwelfare.tn.gov.in](https://www.socialwelfare.tn.gov.in) | State | **NETWORK_ERROR** | None | 129ms | `official` |
| `TN_AGRI` | Department of Agriculture and Farmers Welfare | [https://www.agri.tn.gov.in](https://www.agri.tn.gov.in) | State | **NETWORK_ERROR** | None | 137ms | `official` |
| `TN_TNAU_REF` | Tamil Nadu Agricultural University | [https://www.tnau.ac.in](https://www.tnau.ac.in) | Academic | **ACCESSIBLE** | 200 | 845ms | `trusted_open` |
| `TN_EDUC` | School Education Department | [https://www.tnschools.gov.in](https://www.tnschools.gov.in) | State | **ACCESSIBLE** | 200 | 279ms | `official` |
| `TN_HEALTH` | Health and Family Welfare Department | [https://www.tnhealth.tn.gov.in](https://www.tnhealth.tn.gov.in) | State | **ACCESSIBLE** | 200 | 567ms | `official` |
| `TN_CMCHIS` | Chief Minister's Comprehensive Health Insurance Scheme | [https://www.cmchistn.com](https://www.cmchistn.com) | State | **ACCESSIBLE** | 200 | 510ms | `official` |
| `TN_TANGEDCO` | Tamil Nadu Generation and Distribution Corporation | [https://www.tangedco.gov.in](https://www.tangedco.gov.in) | State | **NETWORK_ERROR** | None | 11161ms | `official` |
| `TN_MAWS` | Municipal Administration and Water Supply Department | [https://www.tnmaws.tn.gov.in](https://www.tnmaws.tn.gov.in) | State | **NETWORK_ERROR** | None | 169ms | `official` |
| `CEN_PMKISAN` | Pradhan Mantri Kisan Samman Nidhi Portal | [https://pmkisan.gov.in](https://pmkisan.gov.in) | Central | **ACCESSIBLE** | 200 | 373ms | `official` |

## Departmental Authority Discrepancy Findings
- **Agriculture Portal Confusion**: The seed dataset mapped `TN_AGRI` to `https://www.tnau.ac.in`. TNAU is Tamil Nadu Agricultural University (an academic and agricultural research institution located in Coimbatore). The administrative authority for schemes and farmer welfare is the **Department of Agriculture and Farmers Welfare, Government of Tamil Nadu** (`https://www.agri.tn.gov.in`). The catalog has been corrected to reference `agri.tn.gov.in` for governance schemes while retaining `tnau.ac.in` under `trusted_open` for agronomic research.
- **e-Sevai Portal Endpoints**: `esevai.tn.gov.in` operates as the primary transactional citizen services portal under TNeGA (`tnega.tn.gov.in`).
- **Open Data Integration**: `https://tn.data.gov.in` is active and responsive (probed successfully), serving as the state's official CKAN-based open dataset repository.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
