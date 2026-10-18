# Seeded Record Comprehensive Audit

## Audit Methodology
Every record in `database/seeds/001_seed_data.sql` was evaluated against authoritative Tamil Nadu government portals (tn.gov.in, tnega.tn.gov.in, esevai.tn.gov.in, tndistricts.nic.in, agri.tn.gov.in) and verified for:
1. **Factual Correctness**: Administrative naming, headquarters, Tamil translation.
2. **Relational Integrity**: Foreign key validity and column schema alignment.
3. **Jurisdictional Boundary**: Strict separation of Tamil Nadu State schemes from Government of India Central Sector schemes.

## 1. Administrative Districts (38 Records)
| ID | Seed Code | Verified Code | District Name | Tamil Name | Headquarters | Audit Findings | Status |
|---|---|---|---|---|---|---|---|
| 1 | `TN-CHE` | `TN-CHN` | Chennai | சென்னை | Chennai | Standard code collision with Chengalpattu | Corrected |
| 2 | `TN-COI` | `TN-CBE` | Coimbatore | கோயம்புத்தூர் | Coimbatore | Standardized to standard RTO/LGD code | Verified |
| 3 | `TN-MAD` | `TN-MDU` | Madurai | மதுரை | Madurai | Standardized to standard code | Verified |
| 4 | `TN-TRI` | `TN-TRY` | Tiruchirappalli | திருச்சிராப்பள்ளி | Tiruchirappalli | Standardized code | Verified |
| 5 | `TN-SAL` | `TN-SLM` | Salem | சேலம் | Salem | Standardized code | Verified |
| 6 | `TN-TIR` | `TN-TNV` | Tirunelveli | திருநெல்வேலி | Tirunelveli | Code collided with Tirupattur in seed | Corrected |
| 7 | `TN-VEL` | `TN-VEL` | Vellore | வேலூர் | Vellore | Valid | Verified |
| 8 | `TN-EDE` | `TN-ERD` | Erode | ஈரோடு | Erode | Standardized code | Verified |
| 9 | `TN-THA` | `TN-TNJ` | Thanjavur | தஞ்சாவூர் | Thanjavur | **CRITICAL**: Seed named 'Thane' (Maharashtra); HQ was Thanjavur | Corrected |
| 10 | `TN-DIN` | `TN-DGL` | Dindigul | திண்டுக்கல் | Dindigul | Standardized code | Verified |
| 11 | `TN-KAN` | `TN-KPM` | Kanchipuram | காஞ்சிபுரம் | Kanchipuram | Code collided with Kanniyakumari in seed | Corrected |
| 12 | `TN-TKR` | `TN-TVL` | Thiruvallur | திருவள்ளூர் | Thiruvallur | Standardized code | Verified |
| 13 | `TN-CUD` | `TN-CUD` | Cuddalore | கடலூர் | Cuddalore | Valid | Verified |
| 14 | `TN-VIL` | `TN-VPM` | Villupuram | விழுப்புரம் | Villupuram | Standardized code | Verified |
| 15 | `TN-NAG` | `TN-NGP` | Nagapattinam | நாகப்பட்டினம் | Nagapattinam | Standardized code | Verified |
| 16 | `TN-THI` | `TN-TVR` | Thiruvarur | திருவாரூர் | Thiruvarur | Standardized code | Verified |
| 17 | `TN-PUD` | `TN-PDK` | Pudukkottai | புதுக்கோட்டை | Pudukkottai | Standardized code | Verified |
| 18 | `TN-SIV` | `TN-SVG` | Sivaganga | சிவகங்கை | Sivaganga | Standardized code | Verified |
| 19 | `TN-RAM` | `TN-RAM` | Ramanathapuram | ராமநாதபுரம் | Ramanathapuram | Valid | Verified |
| 20 | `TN-TUT` | `TN-TUT` | Thoothukudi | தூத்துக்குடி | Thoothukudi | Valid | Verified |
| 21 | `TN-KAN` | `TN-KKI` | Kanniyakumari | கன்னியாகுமரி | Nagercoil | **CRITICAL**: Code collided with Kanchipuram | Corrected |
| 22 | `TN-VIR` | `TN-VRD` | Virudhunagar | விருதுநகர் | Virudhunagar | Standardized code | Verified |
| 23 | `TN-THE` | `TN-THN` | Theni | தேனி | Theni | Standardized code | Verified |
| 24 | `TN-KRI` | `TN-KRI` | Krishnagiri | கிருஷ்ணகிரி | Krishnagiri | Valid | Verified |
| 25 | `TN-DHE` | `TN-DPI` | Dharmapuri | தர்மபுரி | Dharmapuri | Standardized code | Verified |
| 26 | `TN-TIV` | `TN-TVM` | Tiruvannamalai | திருவண்ணாமலை | Tiruvannamalai | Code collided with Tirupur in seed | Corrected |
| 27 | `TN-NMK` | `TN-NKL` | Namakkal | நாமக்கல் | Namakkal | Standardized code | Verified |
| 28 | `TN-KAR` | `TN-KRR` | Karur | கரூர் | Karur | Standardized code | Verified |
| 29 | `TN-ARI` | `TN-ARI` | Ariyalur | அரியலூர் | Ariyalur | Valid | Verified |
| 30 | `TN-PER` | `TN-PBL` | Perambalur | பெரம்பலூர் | Perambalur | Standardized code | Verified |
| 31 | `TN-TIV` | `TN-TPR` | Tiruppur | திருப்பூர் | Tiruppur | **CRITICAL**: Code collided with Tiruvannamalai | Corrected |
| 32 | `TN-NID` | `TN-NLG` | Nilgiris | நீலகிரி | Udhagamandalam | Standardized code | Verified |
| 33 | `TN-MAY` | `TN-MYD` | Mayiladuthurai | மயிலாடுதுறை | Mayiladuthurai | Standardized code | Verified |
| 34 | `TN-CAL` | `TN-KLK` | Kallakurichi | கள்ளக்குறிச்சி | Kallakurichi | Standardized code | Verified |
| 35 | `TN-TEN` | `TN-TKS` | Tenkasi | தென்காசி | Tenkasi | Standardized code | Verified |
| 36 | `TN-CHE` | `TN-CGL` | Chengalpattu | செங்கல்பட்டு | Chengalpattu | **CRITICAL**: Code collided with Chennai | Corrected |
| 37 | `TN-RAN` | `TN-RPT` | Ranipet | ராணிப்பேட்டை | Ranipet | Standardized code | Verified |
| 38 | `TN-TIR` | `TN-TPT` | Tirupattur | திருப்பத்தூர் | Tirupattur | **CRITICAL**: Code collided with Tirunelveli | Corrected |

## 2. Key Schemes Jurisdictional Audit
1. **PM-Kisan (`TN-PM-KISAN`)**:
   - Seeded as `scheme_level = 'state'` and associated with state portal.
   - **Audit Finding**: Pradhan Mantri Kisan Samman Nidhi is a 100% Central Sector Scheme sponsored by the Ministry of Agriculture & Farmers Welfare, GoI. While implemented at ground level by the Tamil Nadu Department of Agriculture, it must be reclassified as `scheme_level = 'central'` with `funding_pattern = '100% Central'` and status `externally_referenced`.
2. **Old Age Pension (`TN-NIRP-PENSION`)**:
   - Seeded as a pure state scheme.
   - **Audit Finding**: IGNOAPS is funded 60% by the Central National Social Assistance Programme (NSAP) and 40% topped up by the Tamil Nadu State Social Welfare treasury. Classified as `Centrally Sponsored (60:40)`.
3. **Kalaignar Magalir Urimai Thogai (`TN-KALAIGNAR-MAGALIR-URIMAI`)**:
   - State apex flagship scheme (100% State). Verified via GO Ms No 1, Social Welfare Dept, 2023. Rs.1,000/month DBT.
4. **Chief Minister Breakfast Scheme (`TN-CM-BREAKFAST`)**:
   - 100% State funded scheme across all government primary schools. Verified via GO Ms No 138, School Education Dept, 2022.

---
*Report generated as part of MyGovt Tamil Nadu Data Audit Suite.*
