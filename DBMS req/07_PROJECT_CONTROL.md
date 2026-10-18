# MyGovt — Project Control Document

Living document. Owner: project lead (rotate weekly). Update at every weekly review.

---

## 1. Project charter
| Item | Value |
|------|-------|
| Project | MyGovt — AI-Powered Citizen Intelligence & State Governance Platform |
| Type | Academic DBMS + AI prototype |
| Duration | ~4 weeks (30 days) |
| Team | 3 members |
| Objective | Deliver a working, explainable, database-first governance assistant covering schemes, services and complaints for Tamil Nadu |
| Success | All acceptance criteria in `00_REQUIREMENTS.md §8` met; demo script runs end-to-end |
| Out of scope | Weather, emergency/disaster, real payments, real submissions, real citizen data |
| Assumptions | Local Docker deployment is enough; synthetic people data; LLM API access available |
| Constraints | Time, LLM cost, availability of ward-level boundaries and Tamil speech quality |

## 2. Roles and responsibilities (RACI)

R = Responsible · A = Accountable · C = Consulted · I = Informed

| Work package | M1 DB+Backend | M2 AI+Data | M3 Frontend+Integration |
|--------------|:---:|:---:|:---:|
| Requirements & PRD | C | C | C (A = rotating lead) |
| Schema, PostGIS, migrations | **A/R** | C | I |
| ETL framework | R | **A/R** | I |
| Seed data & rule authoring | C | **A/R** | C |
| Auth, RBAC, REST APIs | **A/R** | C | C |
| Complaint workflow, SLA, escalation | **A/R** | R (classifier) | C |
| Embeddings, hybrid search, RAG | C | **A/R** | I |
| Knowledge graph | C | **A/R** | I |
| Eligibility, policy, trust, decisions | C | **A/R** | I |
| Frontend, dashboards, GIS map | C | C | **A/R** |
| Voice | I | R | **A/R** |
| Testing & evaluation | R | R | R (A = M2 for AI, M1 for API, M3 for E2E) |
| Security review | **A/R** | C | R |
| Documentation & demo | R | R | **A/R** |

Cross-cover: each critical module has a named backup reviewer (see §9).

## 3. Work breakdown structure (WBS)

```
1 Foundation
  1.1 Repo, Docker, CI                       M1
  1.2 Requirements freeze, ADRs              All
2 Data
  2.1 Source registry                        M2
  2.2 Schema + migrations                    M1
  2.3 GIS boundaries + resolver              M1
  2.4 ETL framework + loaders                M1/M2
  2.5 Seed schemes/services + rules          M2
  2.6 Synthetic data                         M2
3 Intelligence
  3.1 Chunking + embeddings                  M2
  3.2 Hybrid search + RAG                    M2
  3.3 Knowledge graph                        M2
  3.4 Eligibility engine                     M2
  3.5 Policy resolver + trust + decisions    M2
  3.6 Intent/entities/language + LangGraph   M2
4 Application
  4.1 Auth + RBAC                            M1
  4.2 Scheme/Service/Document APIs           M1
  4.3 Complaint workflow + SLA + escalation  M1
  4.4 Complaint classifier + router          M2
  4.5 AI endpoints                           M1/M2
5 Experience
  5.1 Citizen UI                             M3
  5.2 Complaint UI + map                     M3
  5.3 Government + admin dashboards          M3/M1
  5.4 Voice                                  M3/M2
6 Quality
  6.1 Unit/integration                       All
  6.2 AI evaluation + adversarial            M2
  6.3 E2E + accessibility                    M3
  6.4 Security + performance                 M1
7 Delivery
  7.1 Docs + traceability                    All
  7.2 Demo script + rehearsal                M3
  7.3 Final report/presentation              All
```

## 4. Schedule and milestones

| ID | Milestone | Target day | Exit criterion | Owner |
|----|-----------|-----------|----------------|-------|
| MS0 | Kick-off, scope freeze | D2 | MVP list signed | All |
| MS1 | Foundation + schema live | D5 | schema applied, CI green, jurisdiction tests pass | M1 |
| MS2 | Seed data + ETL idempotent | D8 | `make seed` idempotent; source registry complete | M1/M2 |
| MS3 | Search + RAG baseline | D13 | 20 golden queries cited | M2 |
| MS4 | Eligibility + trust + graph | D18 | gold set 100%; graph reconciles | M2 |
| MS5 | API complete | D20 | integration tests + OpenAPI | M1 |
| MS6 | Complaint flow end-to-end | D25 | routing ≥ 90%; escalation test passes | All |
| MS7 | UI + voice + dashboards integrated | D27 | E2E demo passes | M3 |
| MS8 | Hardening + test report | D29 | acceptance criteria met | All |
| MS9 | Demo + submission | D30 | rehearsed demo; docs final | All |

**Critical path:** schema → ETL/seed data → embeddings → retrieval → trust → orchestrator → UI integration. Complaint path (classifier → routing → SLA → escalation) runs in parallel but joins at MS6.

**Buffer:** keep D28–D30 for fixes only; no new features after D27 (feature freeze).

## 5. Weekly cadence
| Ceremony | When | Output |
|----------|------|--------|
| Stand-up (15 min) | Daily | blockers, plan |
| Integration checkpoint | Mon/Thu | `develop` demo build |
| Weekly review | Fri | status report (§10), risks, scope check |
| Retro (20 min) | Fri | 1–3 process changes |

## 6. Scope and change control
1. MVP = PRD features marked **M**. Stretch (**S**) only if the owning milestone is on time.
2. Any change that affects scope, schema or API contract needs a **Change Request (CR)** in `docs/changes/CR-NNN.md`: description, reason, impact (schedule/schema/API/tests), decision.
3. Approval: all three members for scope/schema; module owner + one reviewer for internal changes.
4. Schema changes → Alembic migration + update `03_DATABASE_SCHEMA.md`.
5. API changes → update OpenAPI + frontend client + tests in the same PR.

**CR template**
```
CR-ID:            Date:         Requested by:
Change:
Reason:
Impact: schedule / schema / API / tests / docs
Alternatives considered:
Decision: approved / rejected / deferred     Decided by:
```

## 7. Quality gates

| Gate | Criteria |
|------|----------|
| **PR merge** | lint + type-check + tests green; ≥ 1 review; docs/tests updated; no secrets (detect-secrets) |
| **Milestone exit** | exit criterion in §4 demonstrated live to the team |
| **Release candidate** | all acceptance criteria met; no open P0/P1 defects; security scan done; demo rehearsed |

### Definition of Ready (task)
Clear acceptance criteria · requirement IDs linked · dependencies identified · owner and reviewer assigned.

### Definition of Done (task)
Code merged · tests written and passing · coverage target met · docs/OpenAPI updated · migration included if needed · audit/decision logging in place where required · reviewed.

## 8. Defect management
| Severity | Definition | Response |
|----------|------------|----------|
| P0 | Data exposure, auth bypass, wrong eligibility/routing at scale, data loss | Stop; fix immediately |
| P1 | Core flow broken; AI answers ungrounded | Fix within 24 h |
| P2 | Degraded feature, workaround exists | Fix before release |
| P3 | Cosmetic | Backlog |

Track in GitHub Issues with labels `severity/Px`, `area/*`, `milestone/MSx`.

## 9. Ownership and review map
| Module | Owner | Reviewer |
|--------|-------|----------|
| Schema/migrations | M1 | M2 |
| Auth/RBAC/security | M1 | M3 |
| ETL | M2 (A), M1 | M1 |
| Eligibility/rules | M2 | M1 |
| Trust/policy/decisions | M2 | M1 |
| Complaint API/SLA | M1 | M2 |
| Classifier/router | M2 | M1 |
| Frontend | M3 | M1 |
| Voice | M3 | M2 |

## 10. Weekly status report template
```
Week N · Date
Overall: GREEN / AMBER / RED
Done this week:
Planned next week:
Milestones: MS? — on track / at risk (why)
Risks changed: 
Decisions needed:
Metrics: eligibility gold %, routing %, recall@5, faithfulness %, test coverage, open P0/P1
```

## 11. Risk register

Likelihood (L) and impact (I): 1 low – 5 high. Score = L × I.

| ID | Risk | L | I | Score | Mitigation | Owner | Trigger / contingency |
|----|------|:-:|:-:|:----:|------------|-------|----------------------|
| R1 | Official data hard to scrape/parse (PDF, changing pages) | 4 | 3 | 12 | Start with structured/open sources; cap PDF scope; manual curated seed for 30–50 schemes | M2 | If > 3 days lost → curate manually |
| R2 | Eligibility rules incorrectly extracted | 3 | 5 | 15 | Human review vs. source clause; gold tests; show source link | M2 | Remove scheme from demo if unverified |
| R3 | Ward/local-body polygons unavailable | 4 | 3 | 12 | District+taluk required; synthetic ward polygons labelled; fallback level recorded | M1 | Demo at taluk level |
| R4 | Tamil/Tanglish quality low | 3 | 4 | 12 | Eval set early; confidence thresholds → triage; multilingual embeddings | M2 | Reduce voice to English + Tamil text |
| R5 | LLM cost/latency/rate limits | 3 | 3 | 9 | Caching, small model default, mocked LLM in CI, graceful degradation | M2 | Switch provider/local model |
| R6 | Scope creep | 4 | 4 | 16 | Scope freeze D2, CR process, feature freeze D27 | Lead | Drop S/C items |
| R7 | Integration slip between teams | 3 | 4 | 12 | API contract first (OpenAPI), mocks, twice-weekly integration | All | Pair on blockers |
| R8 | Dataset licence/availability problems | 3 | 3 | 9 | Check licence at registration; store in registry | M2 | Replace with synthetic/curated |
| R9 | Security flaw (authz, upload) | 2 | 5 | 10 | RBAC tests, RLS, upload validation, scans | M1 | Fix before demo; disable feature |
| R10 | Hallucinated or ungrounded answers in demo | 3 | 5 | 15 | Trust layer, citation validation, abstention, adversarial tests | M2 | Pre-script demo questions; keep abstain path ready |
| R11 | Key member unavailable | 2 | 4 | 8 | Cross-review map, documented modules | All | Reassign per §9 |
| R12 | Heavy stack (Postgres+Neo4j+Redis+MinIO+models) overloads laptops | 3 | 3 | 9 | Resource limits; optional services behind flags; shared dev server | M1 | Disable Neo4j/Redis in dev |
| R13 | Embedding model/dimension change late | 2 | 3 | 6 | Decide in ADR-004 by D3; re-embed script | M2 | Re-run `make embed` |
| R14 | Privacy complaints about citizen data in demo | 1 | 4 | 4 | Synthetic only, labelled | All | — |

Review the register every Friday; add new risks immediately.

## 12. Assumptions and dependencies log
| ID | Item | Status | Owner |
|----|------|--------|-------|
| A1 | LLM API key available | open | M2 |
| A2 | Tamil STT/TTS provider chosen and validated | open | M3 |
| A3 | District/taluk boundaries obtained and licence checked | open | M1 |
| A4 | 30–50 seed schemes selected with official URLs | open | M2 |
| A5 | Embedding model downloaded / runnable on team laptops | open | M2 |
| A6 | Map tile source allowed for demo use | open | M3 |

## 13. Decision log (ADR index)
| ID | Decision | Status | Date |
|----|----------|--------|------|
| ADR-001 | PostgreSQL is the system of record | accepted | |
| ADR-002 | Neo4j is a derived, rebuildable projection | accepted | |
| ADR-003 | Rules and policy resolver run before the LLM; LLM only explains | accepted | |
| ADR-004 | Embedding model + dimension (1024) | proposed | |
| ADR-005 | LLM provider and fallback | proposed | |
| ADR-006 | Tamil speech provider | proposed | |
| ADR-007 | Abstain below trust threshold | accepted | |
| ADR-008 | Synthetic data for all people | accepted | |

## 14. Source and dataset control checklist
For **every** source before loading:
- [ ] Registered in `source_registry` (type, URL, format, jurisdiction, access method)
- [ ] URL reachable and content matches the description (record date checked)
- [ ] Licence/terms recorded; redistribution/use allowed for academic project
- [ ] Reliability score assigned with justification
- [ ] Checksum recorded in `dataset_registry`
- [ ] Validation + quality scores computed
- [ ] Quarantine reviewed
- [ ] `verified_at` set for schemes/services after human spot-check (≥ 10% sample or all, for seeded demo items)

> The dataset list in the original blueprint (names, record counts, links) came from the team's research. Treat counts and availability as **unverified** until checked at ingestion time.

## 15. Metrics dashboard (track weekly)
| Metric | Target | W1 | W2 | W3 | W4 |
|--------|--------|----|----|----|----|
| Seed schemes loaded + reviewed | 30–50 | | | | |
| Services loaded | 20–30 | | | | |
| Eligibility gold pass % | ≥ 95 | | | | |
| Retrieval recall@5 | ≥ 0.80 | | | | |
| RAG faithfulness % | ≥ 90 | | | | |
| Routing accuracy % | ≥ 90 | | | | |
| Intent accuracy % (ta/en/tanglish) | ≥ 85 | | | | |
| Unit coverage % | ≥ 70 (rules ≥ 90) | | | | |
| Open P0/P1 defects | 0 | | | | |
| p95 chat latency (s) | ≤ 8 | | | | |

## 16. Traceability matrix (starter)
Maintain `docs/traceability.csv`: `PRD feature | SRS ID | table(s) | endpoint(s) | test(s) | status`.

| PRD | SRS | Tables | Endpoint | Test |
|-----|-----|--------|----------|------|
| F-03 | SCH-04..07 | schemes.eligibility_rule | POST /schemes/check-eligibility | test_eligibility_gold |
| F-22 | CMP-04, GIS-02 | administration.* | GET /gis/jurisdiction | test_jurisdiction |
| F-27 | CMP-09 | complaints.escalation | worker job | test_escalation_idempotent |
| F-45 | AI-09, AI-13 | ai.decision, decision_lineage | GET /ai/decisions/{id} | test_lineage |
| F-46 | AI-07 | ai.decision.abstained | POST /ai/chat | test_abstain |

## 17. Communication plan
- Chat channel for daily; GitHub Issues/Projects for work tracking; PR descriptions link requirement IDs.
- Faculty/mentor updates: end of each week with the status report.
- Demo rehearsals: D26, D28, D29.

## 18. Configuration and release management
- Versioning: semantic tags `v0.x`; tag each milestone.
- Data versioning: dataset checksums + `dataset_registry.version`; demo DB snapshot taken at D29 (`pg_dump`) and stored with the tag.
- Environments: `local` (compose), optional `demo` (single VM). No separate prod.
- Rollback: restore snapshot + redeploy previous tag.

## 19. Ethics, privacy and compliance checklist
- [ ] Prototype uses synthetic personal data only
- [ ] No Aadhaar/ID numbers anywhere (code, DB, logs)
- [ ] Consent captured before profile-based matching
- [ ] Disclaimer shown in UI (not an official portal; verify on official site)
- [ ] Anonymous corruption-report path does not log identifying data
- [ ] Logs exclude tokens, passwords, and full complaint text where unnecessary
- [ ] LLM provider data-retention settings reviewed; no real PII sent
- [ ] Dataset licences respected and attributed
- [ ] Bias check: eligibility and routing outcomes reviewed across districts/categories for unexpected disparities
- [ ] If ever deployed for real users: obtain legal review (data protection law, government-data reuse terms) — not covered by this prototype

## 20. Closure checklist
- [ ] Acceptance criteria met and recorded in `docs/TEST_REPORT.md`
- [ ] Known limitations documented (`docs/LIMITATIONS.md`)
- [ ] Final report, slides, demo video
- [ ] Repo tagged; DB snapshot archived
- [ ] Lessons learned captured
