# Service data completeness (2026-10-20)

Generated from `etl/content/services_content.py` and `data/content/esevai_service_list_2023-04-10.json` (rows copied from the official list).

## Source

The **official Tamil Nadu e-Sevai Service List** (`https://www.tnesevai.tn.gov.in/Pages/ServiceList.aspx`, *Last Updated: 10/04/2023*) was downloaded and parsed. It gives, per service, the stipulated timeline, the fee, the service-centre charge and the document list. It is **more than three years old**, so every fee and timeline is labelled with that date and a note to confirm on the live portal. Earlier seed values that the list does not support (for example processing times of 3 / 7 / 15 / 30 days and an Rs.100 EC fee) were **removed**.

## Completeness

| Field | Services (of 21) |
|---|---|
| Present on the official e-Sevai list | 20 |
| Document list taken from the official list (`required`) | 16 |
| Document list compiled (unverified) or absent | 5 |
| Official stipulated timeline | 5 |
| Fee / service charge shown (labelled 2023) | 20 |
| No official fee, timeline or document list (shown as not confirmed) | 1 |
| Tamil name | 21 |
| Tamil description | 21 |

The project reference lists 20 services but numbers 21; all 21 are included.

## Per service

| Code | Official row | Official documents | Timeline | Fee |
|---|---|---|---|---|
| SVC-PATTA-TRANSFER | - | no | - | not listed |
| SVC-BIRTH-CERT | 44,50 | no | - | The e-Sevai list shows no application fee and a service charge of Rs.100 for printing a birth certificate (Directorate of Public Health) and Rs.40 (Greater Chennai Corporation). |
| SVC-COMM-CERT | 62 | yes | - | fee 0 + charge 60 |
| SVC-DEATH-CERT | 45,51 | no | - | The e-Sevai list shows no application fee and a service charge of Rs.100 for printing a death certificate (Directorate of Public Health) and Rs.40 (Greater Chennai Corporation). |
| SVC-ENCUMB-CERT | 56,58 | no | - | The e-Sevai list shows no application fee and a service charge of Rs.10 for issuance of an EC and Rs.2 for EC download. Statutory search fees on TNREGINET are not listed there. |
| SVC-FIRST-GRAD | 65 | yes | - | fee 0 + charge 60 |
| SVC-INCOME-CERT | 64 | yes | 15 days | fee 0 + charge 60 |
| SVC-LEGAL-HEIR | 73 | yes | - | fee 0 + charge 60 |
| SVC-NATIVITY | 63 | yes | 07 Days | fee 0 + charge 60 |
| SVC-RATION-SMART | 9 | no | - | fee 0 + charge 60 |
| SVC-DESERTED-WOMAN-CERT | 66 | yes | 15 Days | fee 0 + charge 60 |
| SVC-AGRI-INCOME-CERT | 67 | yes | - | fee 0 + charge 60 |
| SVC-FAMILY-MIGRATION-CERT | 68 | yes | - | fee 0 + charge 60 |
| SVC-UNEMPLOYMENT-CERT | 69 | yes | - | fee 0 + charge 60 |
| SVC-WIDOW-CERT | 70 | yes | - | fee 0 + charge 60 |
| SVC-INTERCASTE-MARRIAGE-CERT | 72 | yes | 15 Days | fee 0 + charge 60 |
| SVC-OBC-CERT | 74 | yes | - | fee 0 + charge 60 |
| SVC-RESIDENCE-CERT | 75 | yes | - | fee 0 + charge 60 |
| SVC-SMALL-FARMER-CERT | 76 | yes | - | fee 0 + charge 60 |
| SVC-SOLVENCY-CERT | 77 | yes | - | fee 0 + charge 60 |
| SVC-UNMARRIED-CERT | 79 | yes | 15 Days | fee 0 + charge 60 |
