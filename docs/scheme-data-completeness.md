# Scheme data completeness (2026-10-20)

Generated from `etl/content/schemes_content.py`. The project reference lists 30 scheme entries; entries 19 and 30 are the same scheme (marriage assistance to differently abled persons) and are merged, giving 29 scheme records.

## Sources

* The project's compiled scheme reference (a PDF supplied with the task) - **not an official source** and says so itself.
* Official pages actually read on the research date: PM-KISAN portal, Commissionerate for Welfare of the Differently Abled (marriage assistance), TN AgriSnet sericulture schemes, Mudhalvar Marundhagam instructions, and the official **e-Sevai Service List** (document lists for the pension schemes and CMUPT).
* The Commissionerate of Revenue Administration pages (`cra.tn.gov.in/...`) cited in the reference **returned 404** on the research date. Pension amounts (Rs.1,200 / Rs.1,500) come from a search-engine snapshot of that official page (as of March 2024) and are stored as `historical`.
* For Kalaignar Magalir Urimai, CMCHIS, Pudhumai Penn and Innuyir Kappom no official page could be read; the criteria come from news reports and are stored as unverified, with the conflicts shown (for example CMCHIS income limit Rs.1,20,000 vs Rs.72,000; the cover increase to Rs.25 lakh is reported but unconfirmed).

## Completeness

| Field | Schemes with data (of 29) |
|---|---|
| Eligibility conditions | 29 |
| Exclusions | 2 (only where stated) |
| Benefits | 29 |
| Required documents | 29 |
| Application procedure | 29 |
| Tamil name (all existing records keep their seeded Tamil name) | 29 |
| Tamil short description | 29 |
| Fields read on an official page | 13 schemes (21 fields) |

Benefit amounts by confidence: historical: 14, not_applicable: 9, unverified: 5, varies: 3, verified_current: 4.

Document levels: category_specific: 6, conditional: 27, recommended: 4, required: 41, unverified: 50. `required` is used only where an official source names the document for that scheme; the rest are `unverified` (compiled), `conditional` or `category_specific`.

## What remains unverified

Every scheme stays `provisional` (one is `externally_referenced`); none was promoted to `official_verified`. Application windows/deadlines are not stated for any scheme because none was confirmed. The Tamil text of eligibility, exclusion, step and benefit prose is **not translated**: it is shown in English (marked `lang="en"`) with a notice in Tamil mode; only names, short descriptions and interface text are in Tamil.

## Per scheme

| Code | Eligibility | Benefits | Documents | Steps | Official-page fields |
|---|---|---|---|---|---|
| TN-AMMA-BABY-CARE | 3 | 1 | 3 | 3 | - |
| TN-AMMA-UNAVAGAM | 2 | 1 | 1 | 2 | - |
| TN-PATTA-CHITTA | 2 | 1 | 3 | 3 | - |
| TN-CM-BREAKFAST | 2 | 1 | 1 | 2 | - |
| TN-CM-HEALTH-INS | 3 | 1 | 4 | 4 | - |
| TN-DISABILITY-PENSION | 3 | 1 | 8 | 3 | documents |
| TN-FREE-BUS-PASS | 2 | 1 | 2 | 2 | - |
| TN-KALAIGNAR-MAGALIR-URIMAI | 3 | 1 | 4 | 3 | - |
| TN-MAKKALAI-THEDI | 2 | 1 | 3 | 2 | - |
| TN-MOOVALUR-RAMAMIRTHAM | 3 | 1 | 4 | 3 | - |
| TN-NIRP-PENSION | 3 | 1 | 7 | 3 | documents |
| TN-PM-KISAN | 2 | 1 | 4 | 3 | benefit, exclusions, eligibility |
| TN-TAMIL-PUDHALVAN | 3 | 1 | 5 | 3 | - |
| TN-NAAN-MUDHALVAN | 2 | 1 | 4 | 3 | - |
| TN-CM-GIRL-CHILD | 3 | 2 | 5 | 3 | - |
| TN-KANAVU-ILLAM | 3 | 1 | 5 | 4 | - |
| TN-EVR-MANIAMMAIYAR | 3 | 2 | 6 | 4 | listed |
| TN-ANNAI-TERESA | 3 | 2 | 4 | 3 | listed |
| TN-MARRIAGE-DIFF-ABLED | 3 | 2 | 3 | 3 | benefit, eligibility, documents, application |
| TN-MULBERRY-ASSISTANCE | 4 | 1 | 7 | 4 | benefit, eligibility, documents |
| TN-MUDHALVAR-MARUNDHAGAM | 4 | 1 | 4 | 4 | eligibility, application |
| TN-CMUPT | 3 | 1 | 8 | 3 | documents |
| TN-INNUYIR-KAPPOM | 2 | 1 | 3 | 3 | - |
| TN-DWPS | 2 | 1 | 9 | 3 | documents |
| TN-MUTHULAKSHMI-MATERNITY | 3 | 1 | 4 | 3 | - |
| TN-MAGAPERU-SANJEEVI | 2 | 1 | 3 | 2 | - |
| TN-SEWING-MACHINE | 2 | 1 | 4 | 3 | listed |
| TN-WIDOW-REMARRIAGE | 3 | 2 | 5 | 3 | listed |
| TN-INTERCASTE-MARRIAGE | 3 | 2 | 5 | 3 | listed |
