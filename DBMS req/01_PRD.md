# MyGovt — Product Requirements Document (PRD)

**Product:** MyGovt — AI-Powered Citizen Intelligence & State Governance Platform
**Tagline:** Your Government. Your Services. Your Voice.
**Scope region:** Tamil Nadu (prototype)
**Document version:** 1.0 · **Status:** Draft for team review
**Project type:** Academic DBMS + AI prototype (3 members, ~4 weeks)

---

## 1. Problem statement

Citizens in Tamil Nadu must navigate dozens of departments, portals and documents to (a) find schemes they qualify for, (b) learn which service/certificate they need and what it costs, and (c) report civic problems and know whether anyone acts on them. Information is scattered across PDFs, GOs, department sites and e-Sevai pages, mostly in formal English or Tamil. Complaint routing depends on the citizen knowing which department/authority owns a problem in their ward.

Generic government chatbots fail here because an LLM answering from memory can be **wrong, outdated, or for the wrong jurisdiction** — and in governance, a wrong answer has real cost.

## 2. Vision

One conversational and form-based interface where a citizen can discover, verify and act on government information, with every answer **traceable to an official source and a rule**, and every complaint **routed deterministically, tracked against an SLA, and escalated when ignored**.

**Core principle:** Official data → structured database → retrieval → deterministic rules → verification → AI explanation → action → audit. *The LLM is never the source of truth.*

## 3. Goals and non-goals

### 3.1 Goals
| ID | Goal | Measure |
|----|------|---------|
| G1 | Citizens can find schemes they are eligible for with an explanation | Eligibility engine matches gold-set labels ≥ 95% |
| G2 | Every factual answer is grounded and cited | ≥ 90% of answers carry ≥ 1 verified citation; hallucination rate on eval set ≤ 5% |
| G3 | Complaints are routed to the right authority from location + category | Routing accuracy ≥ 90% on synthetic test set |
| G4 | SLA tracking and automatic escalation work end-to-end | 100% of overdue complaints in test data escalate within one scheduler cycle |
| G5 | Tamil, English and Tanglish input work | Intent accuracy ≥ 85% on mixed-language test set |
| G6 | Every AI decision is auditable | 100% of decisions have a `decision` row + lineage |

### 3.2 Non-goals (explicitly out of scope)
- Weather forecasting; emergency / disaster services (explicitly excluded by the team).
- Real payment processing, real e-Sevai submission, or any real integration that files applications on behalf of citizens.
- Real citizen PII; Aadhaar or any government-ID number storage or verification.
- Replacing official portals — MyGovt links out to the official application route.
- Legal advice. MyGovt informs; it does not interpret law for individual disputes.

## 4. Users and personas

| Persona | Description | Key needs |
|---------|-------------|-----------|
| **Priya — Citizen (student, 21, rural Coimbatore)** | Smartphone user, prefers Tamil | "What can I apply for?", required documents, simple language |
| **Murugan — Citizen (46, auto driver, urban)** | Low literacy, voice-first | Speak a complaint, get a complaint ID, see status |
| **Officer — Ward/Zonal officer** | Handles assigned complaints | Queue, SLA clock, evidence, status update |
| **Department Admin** | Oversees department complaints and data | Performance dashboard, breaches, reassign |
| **State Admin / Data Steward** | Maintains master data and sources | Source registry, dataset versions, data quality |
| **System Admin** | Operates the platform | Users, roles, audit logs, health |

## 5. Feature set

Priority uses MoSCoW. **M** = in MVP, **S** = should (stretch within 4 weeks), **C** = could (post-MVP).

### 5.1 Discovery & information
| ID | Feature | Pri |
|----|---------|-----|
| F-01 | Scheme search (keyword + semantic + filters: dept, category, level) | M |
| F-02 | Scheme detail: benefits, rules, documents, official link, last-verified date | M |
| F-03 | Scheme eligibility check (profile form and natural-language) with per-rule pass/fail | M |
| F-04 | Recommended schemes from citizen profile | M |
| F-05 | Government service search (e-Sevai): fee, charge, requirements, route | M |
| F-06 | Required-documents finder ("how can I prove where I live?") | M |
| F-07 | Government Orders / notices / announcements search | S |
| F-08 | Laws, rules, policy search with version-aware "current rule" answers | S |
| F-09 | Nearby government facilities (map) | S |
| F-10 | Ask MyGovt — conversational assistant (text) with citations | M |
| F-11 | Voice input/output (Tamil/English) | S |

### 5.2 Complaints & accountability
| ID | Feature | Pri |
|----|---------|-----|
| F-20 | Submit complaint (text; voice optional) with map pin / GPS | M |
| F-21 | Auto-classification: category, priority, language, location | M |
| F-22 | Jurisdiction resolution via PostGIS (ward → local body → taluk → district) | M |
| F-23 | Deterministic routing to department + authority | M |
| F-24 | Complaint ID, status timeline, citizen tracking | M |
| F-25 | Officer assignment and officer work queue | M |
| F-26 | SLA calculation, overdue detection | M |
| F-27 | Automatic escalation up the authority chain | M |
| F-28 | Evidence upload (image/pdf/audio/video) with hash | S |
| F-29 | Corruption/bribery report (anonymous option, restricted visibility) | S |
| F-30 | Citizen reopen / rate resolution | C |

### 5.3 Intelligence & trust
| ID | Feature | Pri |
|----|---------|-----|
| F-40 | Intent detection + entity extraction | M |
| F-41 | Hybrid retrieval (SQL + FTS + pgvector + graph) | M |
| F-42 | Trust layer (source, freshness, jurisdiction, effective-date, consistency) | M |
| F-43 | Policy resolver (current valid version for a date + jurisdiction) | S |
| F-44 | Actionability gate (inform vs. guide vs. act) | M |
| F-45 | Decision lineage + "Why this answer?" panel | M |
| F-46 | Abstention ("I can't verify this") when trust is below threshold | M |

### 5.4 Dashboards & administration
| ID | Feature | Pri |
|----|---------|-----|
| F-60 | Citizen dashboard | M |
| F-61 | Government (officer/department) dashboard: counts, SLA, heatmap | M |
| F-62 | Admin console: users, departments, authorities, sources, datasets, AI decisions, audit | S |
| F-63 | Data-quality report per dataset | S |

## 6. Representative user stories

**Scheme discovery**
- *As a citizen*, I enter my age, gender, income and district so that I see schemes I qualify for **and** schemes I narrowly miss with the exact failing rule.
- *As a citizen*, I ask in Tamil "நான் என்ன திட்டங்களுக்கு விண்ணப்பிக்கலாம்?" and get an answer in Tamil with citations.
- *As a citizen*, when my profile lacks a required attribute (e.g., income), I'm told "not enough information" and asked for that attribute — I am **not** told I'm ineligible.

**Services**
- *As a citizen*, I ask "I want to apply for an income certificate" and see the service, fee, documents, processing time and the official application link.

**Complaints**
- *As a citizen*, I report "street light not working for two weeks" with a map pin and receive `MYG-2026-000127`, the responsible authority and the SLA.
- *As an officer*, I see my queue sorted by SLA risk and can update status with remarks.
- *As a department admin*, I see which complaints breached SLA and who they escalated to.

**Trust**
- *As any user*, I can open "Why this answer?" and see the sources, rules, policy version and confidence behind it.

## 7. Key user journeys (summary)
1. **Ask → Answer:** question → intent → retrieval → trust → LLM explanation → citations → lineage.
2. **Eligibility:** profile → deterministic rules → ELIGIBLE / NOT_ELIGIBLE / INSUFFICIENT_DATA → explanation.
3. **Complaint:** text/voice → classify → locate → resolve jurisdiction → route → SLA → track → escalate.
4. **Officer:** queue → update → resolve → citizen notified.

Detailed flows are in `04_FLOW_DOCUMENT.md`.

## 8. Functional principles (product rules)
1. **Database first.** Facts shown to citizens come from the database or cited documents.
2. **Rules decide, LLM explains.** Eligibility, routing and policy validity are deterministic.
3. **Abstain over guess.** Below trust threshold → say so and point to the official source.
4. **Jurisdiction-aware.** Never present a district/local rule to someone outside it.
5. **Time-aware.** Answers use the policy version valid on the query date.
6. **Auditable.** Every decision and mutation is logged.
7. **LLM is read-only.** It can never write SQL or mutate data; actions go through backend APIs.
8. **Privacy by default.** Synthetic data in the prototype; minimum profile collection; consent recorded.

## 9. Success metrics

| Category | Metric | Target |
|----------|--------|--------|
| Correctness | Eligibility gold-set accuracy | ≥ 95% |
| Grounding | Answers with verified citation | ≥ 90% |
| Safety | Answers asserting unverifiable facts | ≤ 5% |
| Routing | Category accuracy / authority accuracy | ≥ 85% / ≥ 90% |
| Latency | p95 chat answer | ≤ 8 s (text) |
| Latency | p95 non-AI API | ≤ 500 ms |
| Reliability | SLA/escalation job success | 100% in test runs |
| Usability | Task completion in a 5-person usability test | ≥ 80% |
| Data | Source-registry coverage of loaded data | 100% |

## 10. Release plan (4 weeks)

| Week | Milestone | Exit criterion |
|------|-----------|----------------|
| 1 | Architecture, schema, seed data | `schema.sql` applied; departments, districts, 30 schemes, 20 services loaded |
| 2 | ETL, documents, embeddings, hybrid search/RAG | Search returns cited results on 20 test queries |
| 3 | Graph, eligibility, trust layer, complaint classifier | Eligibility gold set passes; routing tests pass |
| 4 | FastAPI + UI + complaints + dashboards + voice + test | End-to-end demo script runs |

## 11. Risks and mitigations (product)
| Risk | Impact | Mitigation |
|------|--------|------------|
| Scheme data outdated/incorrect | Wrong guidance | `verified_at`, source link on every item, disclaimer, abstention |
| Eligibility rules mis-extracted from text | Wrong result | Human-reviewed rule set for seeded schemes; LLM-assisted extraction only as a proposal |
| Admin boundary data unavailable at ward level | Routing quality | District + taluk first; synthetic ward polygons for demo, labelled as such |
| Tamil/Tanglish quality | Misclassification | Confidence threshold → triage queue; evaluate on labelled set |
| Scope creep | Missed deadline | MVP freeze at end of week 1; change control (see Project Control doc) |
| Dataset licensing | Legal | Record license in `source_registry`; use only permitted data |

## 12. Open questions (to resolve in week 1)
1. Which exact schemes (30–50) are in the seed set, and who reviews their rules?
2. Which LLM and embedding model (cost, Tamil quality, offline availability)?
3. Which speech provider for Tamil STT/TTS?
4. Will ward-level boundaries be real (TNGIS/OSM) or synthetic for the demo?
5. Is deployment required beyond local Docker (e.g., a college server)?

## 13. Disclaimer text (UI requirement)
> MyGovt provides information compiled from official sources and may not reflect the latest changes. It is not an official government portal and does not constitute legal advice. Always confirm details on the official website before applying.
