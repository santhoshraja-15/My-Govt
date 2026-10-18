# MyGovt — Software Requirements Specification (SRS)

Version 1.0 · Companion to `01_PRD.md`. Requirement keywords: **MUST**, **SHOULD**, **MAY** (RFC 2119).
Priority: **P0** = MVP, **P1** = stretch, **P2** = post-MVP.

---

## 1. Purpose and scope
MyGovt is a web platform for Tamil Nadu citizens to discover schemes and services, check eligibility, search official documents, and file and track civic complaints, supported by a retrieval-and-rules AI layer. Weather and emergency/disaster services are **out of scope**.

## 2. Definitions
| Term | Meaning |
|------|---------|
| Scheme | A government benefit programme (central, state or district) |
| Service | A transactional/government service (e.g., e-Sevai certificate) |
| GO | Government Order |
| SLA | Service-level agreement: maximum time to resolve/escalate a complaint |
| RAG | Retrieval-augmented generation |
| KG | Knowledge graph (Neo4j) |
| Trust layer | Verification step between retrieval and LLM |
| Decision lineage | Stored chain of evidence/rules/sources behind a decision |
| Abstain | System declines to answer because evidence is insufficient |

## 3. Functional requirements

### 3.1 Authentication & authorization (AUTH)
| ID | Requirement | Pri |
|----|-------------|-----|
| AUTH-01 | The system MUST support registration/login with email or phone + password; passwords MUST be hashed with argon2id or bcrypt | P0 |
| AUTH-02 | The system MUST issue short-lived JWT access tokens and refresh tokens | P0 |
| AUTH-03 | The system MUST enforce RBAC for roles: citizen, officer, department_admin, state_admin, system_admin, ai_readonly, etl_user | P0 |
| AUTH-04 | Citizens MUST only read their own profile, conversations, complaints and decisions | P0 |
| AUTH-05 | Officers MUST only see complaints for their authority/jurisdiction (and subordinates, for admins) | P0 |
| AUTH-06 | Login endpoints MUST be rate-limited; repeated failures MUST lock the account temporarily | P1 |
| AUTH-07 | OTP-based phone login MAY be supported (mock provider in prototype) | P2 |

### 3.2 Citizen profile & consent (PROF)
| ID | Requirement | Pri |
|----|-------------|-----|
| PROF-01 | The system MUST allow a citizen to create/update a profile with: date of birth, gender, occupation, student flag, annual income, social category, disability, BPL, residence type, district/taluk/local body, held documents | P0 |
| PROF-02 | The system MUST collect only attributes referenced by the eligibility-attribute registry | P0 |
| PROF-03 | The system MUST record consent before using the profile for personalised matching | P0 |
| PROF-04 | The system MUST NOT store Aadhaar or other government ID numbers | P0 |
| PROF-05 | A citizen MUST be able to delete their profile and see what is stored | P1 |

### 3.3 Schemes (SCH)
| ID | Requirement | Pri |
|----|-------------|-----|
| SCH-01 | MUST list/search schemes by keyword, category, department, level, status | P0 |
| SCH-02 | MUST support semantic search over scheme text in English and Tamil | P0 |
| SCH-03 | MUST show benefits, required documents, application URL, official URL, source and `verified_at` | P0 |
| SCH-04 | MUST evaluate eligibility with a deterministic rule engine returning one of `ELIGIBLE`, `NOT_ELIGIBLE`, `INSUFFICIENT_DATA` | P0 |
| SCH-05 | For every rule, MUST return pass / fail / unknown with the citizen's value, the rule threshold and a human-readable reason | P0 |
| SCH-06 | MUST NOT mark a citizen ineligible because an attribute is missing; MUST list the missing attributes | P0 |
| SCH-07 | MUST support rule groups (AND within group, OR across groups) | P0 |
| SCH-08 | MUST exclude schemes whose `effective_to` has passed or status ≠ active (configurable to show closed) | P0 |
| SCH-09 | MUST rank recommended schemes: eligible first, then near-miss (one failing rule), then insufficient data | P1 |
| SCH-10 | The engine MUST be an ordinary code path with unit tests, with no LLM call | P0 |

### 3.4 Services (SVC)
| ID | Requirement | Pri |
|----|-------------|-----|
| SVC-01 | MUST search services by name/category/department with keyword + semantic search | P0 |
| SVC-02 | MUST show fee, service charge, required documents, processing time and official route | P0 |
| SVC-03 | MUST link scheme document requirements to services that issue them where known (e.g., Income Certificate) | P1 |
| SVC-04 | MUST NOT submit applications on the citizen's behalf | P0 |
| SVC-05 | SHOULD show nearby facilities using PostGIS | P1 |

### 3.5 Documents, policies, laws (DOC)
| ID | Requirement | Pri |
|----|-------------|-----|
| DOC-01 | MUST store documents with type, department, source, hash, dates, language and status | P0 |
| DOC-02 | MUST chunk documents with page and section metadata and embed each chunk | P0 |
| DOC-03 | MUST support full-text, trigram and vector search on chunks | P0 |
| DOC-04 | Policies MUST be versioned; versions MUST NOT overlap in effective period | P0 |
| DOC-05 | The policy resolver MUST return the version valid for (policy, date, jurisdiction) | P1 |
| DOC-06 | Superseded documents MUST remain stored and searchable only when history is requested | P1 |
| DOC-07 | Duplicate documents MUST be detected by file hash | P0 |

### 3.6 Complaints (CMP)
| ID | Requirement | Pri |
|----|-------------|-----|
| CMP-01 | MUST allow a citizen to submit a complaint with text, optional location (GPS/map pin/address) and optional evidence | P0 |
| CMP-02 | MUST classify category, priority and language; MUST record classifier confidence | P0 |
| CMP-03 | If classifier confidence < threshold (default 0.60) the complaint MUST go to a triage queue instead of auto-routing | P0 |
| CMP-04 | MUST resolve jurisdiction from coordinates through PostGIS (ward → local body → taluk → district) | P0 |
| CMP-05 | MUST route using deterministic `routing_rule` (category × jurisdiction) — never by the LLM alone | P0 |
| CMP-06 | MUST generate a unique complaint reference `MYG-YYYY-NNNNNN` | P0 |
| CMP-07 | MUST compute `due_date` and `escalation_due_at` from `sla_rule` | P0 |
| CMP-08 | MUST record every status change in `complaint_history` | P0 |
| CMP-09 | MUST detect SLA breach and escalate to the parent authority automatically; escalation MUST be recorded | P0 |
| CMP-10 | Citizens MUST see status timeline, responsible authority and SLA | P0 |
| CMP-11 | Officers MUST be able to accept, update status, add notes (internal/public) and resolve | P0 |
| CMP-12 | MUST accept evidence (image/pdf/audio/video) with type/size validation and SHA-256 hash | P1 |
| CMP-13 | Corruption reports MUST support anonymous submission and restricted visibility (state-level role only) | P1 |
| CMP-14 | Duplicate complaints (same category within X metres and Y days) SHOULD be flagged | P1 |
| CMP-15 | Complaints MUST NOT be deletable | P0 |

### 3.7 AI assistant (AI)
| ID | Requirement | Pri |
|----|-------------|-----|
| AI-01 | MUST detect intent among: scheme_discovery, eligibility_check, service_info, document_search, policy_query, complaint, complaint_status, greeting, out_of_scope | P0 |
| AI-02 | MUST extract entities: age, gender, income, location, category, department, scheme/service names, dates, durations | P0 |
| AI-03 | MUST detect language: English, Tamil, Tanglish | P0 |
| AI-04 | MUST retrieve evidence by hybrid search, applying hard filters (jurisdiction, effective date, status) **before** scoring | P0 |
| AI-05 | MUST pass the LLM only verified context and instruct it to answer solely from that context | P0 |
| AI-06 | Every factual claim in an answer MUST map to a citation to a stored source | P0 |
| AI-07 | MUST abstain when overall trust < threshold (default 0.70) or no relevant evidence | P0 |
| AI-08 | MUST run the actionability gate: `inform`, `guide`, or `act` | P0 |
| AI-09 | MUST store each decision and its lineage | P0 |
| AI-10 | The AI database role MUST be read-only on knowledge tables and have no access to identity/complaint/audit tables | P0 |
| AI-11 | The LLM MUST NOT generate or execute SQL, Cypher, or shell commands | P0 |
| AI-12 | MUST resist prompt injection from retrieved documents (treat as data; strip instructions) | P1 |
| AI-13 | Users MUST be able to open "Why this answer?" | P0 |
| AI-14 | Voice: STT → pipeline → TTS for Tamil and English | P1 |

### 3.8 GIS (GIS)
| ID | Requirement | Pri |
|----|-------------|-----|
| GIS-01 | MUST store boundaries as `geometry(MultiPolygon,4326)` with GiST indexes | P0 |
| GIS-02 | MUST expose a jurisdiction resolver API (lon/lat → ward/local body/taluk/district/authority) | P0 |
| GIS-03 | MUST render a map with complaint markers and a heatmap for officers | P1 |
| GIS-04 | MUST handle points outside Tamil Nadu by returning "outside supported area" | P0 |

### 3.9 Dashboards (DSH)
| ID | Requirement | Pri |
|----|-------------|-----|
| DSH-01 | Citizen dashboard: recommended schemes, my complaints, recent notices, Ask box | P0 |
| DSH-02 | Government dashboard: totals by status, SLA breaches, escalations, average resolution time, by district/department | P0 |
| DSH-03 | Admin console: users, departments, authorities, officers, sources, datasets, AI decisions, audit logs | P1 |
| DSH-04 | Data-quality scorecard per dataset (completeness, accuracy, consistency, freshness, reliability) | P1 |

### 3.10 Data ingestion & governance (ETL)
| ID | Requirement | Pri |
|----|-------------|-----|
| ETL-01 | Every loaded record MUST trace to a `source_registry` row (and a `dataset_registry` row for file loads) | P0 |
| ETL-02 | Raw files MUST be immutable; their SHA-256 MUST be recorded | P0 |
| ETL-03 | The pipeline MUST be: download → checksum → raw → extract → profile → clean → normalise → dedupe → validate → stage → production → index → graph | P0 |
| ETL-04 | Failing records MUST go to quarantine with a reason; they MUST NOT reach production | P0 |
| ETL-05 | Re-running a load MUST be idempotent | P0 |
| ETL-06 | Each dataset MUST receive a quality score | P1 |
| ETL-07 | Open datasets (Hugging Face/GitHub/Kaggle) MUST be license-checked before use; license stored | P0 |

### 3.11 Knowledge graph (KG)
| ID | Requirement | Pri |
|----|-------------|-----|
| KG-01 | PostgreSQL is the system of record; Neo4j is a derived, rebuildable projection | P0 |
| KG-02 | The graph MUST be rebuildable from PostgreSQL with one command | P0 |
| KG-03 | Node types: State, District, Taluk, LocalBody, Ward, Department, Authority, Scheme, Service, Document, Policy, GO, ComplaintCategory | P0 |
| KG-04 | Relation types: CONTAINS, MANAGES, PROVIDES, ISSUES, REQUIRES, GOVERNED_BY, AVAILABLE_IN, ESCALATES_TO, HANDLES | P0 |

## 4. Non-functional requirements

### 4.1 Performance
| ID | Requirement |
|----|-------------|
| NFR-P1 | p95 latency of non-AI REST endpoints ≤ 500 ms with seed data |
| NFR-P2 | p95 text-chat answer ≤ 8 s; first token streamed ≤ 2 s |
| NFR-P3 | Jurisdiction resolution ≤ 100 ms (GiST-indexed) |
| NFR-P4 | Hybrid search over ≤ 100k chunks ≤ 800 ms before LLM |

### 4.2 Security & privacy
| ID | Requirement |
|----|-------------|
| NFR-S1 | HTTPS everywhere; HSTS in non-dev |
| NFR-S2 | Parameterised queries only; ORM or prepared statements |
| NFR-S3 | Input validation with Pydantic models; file uploads validated by MIME, magic bytes and size |
| NFR-S4 | Secrets in environment/secret store; never in git |
| NFR-S5 | Separate DB roles: `mygovt_app`, `mygovt_ai_readonly`, `mygovt_etl`, `mygovt_admin` |
| NFR-S6 | Audit log is append-only |
| NFR-S7 | PII fields minimised; synthetic data in prototype; consent recorded (aligned with the intent of India's DPDP Act 2023 — confirm exact obligations before any real deployment) |
| NFR-S8 | CORS allow-list; CSRF protection for cookie flows; security headers |
| NFR-S9 | Dependency scanning (pip-audit / npm audit) in CI |
| NFR-S10 | LLM prompts/outputs containing PII MUST NOT be sent to third parties without explicit configuration |

### 4.3 Reliability & operability
| ID | Requirement |
|----|-------------|
| NFR-R1 | One-command local start via Docker Compose |
| NFR-R2 | DB migrations versioned (Alembic) and reversible |
| NFR-R3 | Health endpoints for API, DB, Neo4j, Redis |
| NFR-R4 | Structured JSON logs with request/decision IDs |
| NFR-R5 | Scheduler jobs (SLA, escalation) idempotent and observable |
| NFR-R6 | Graceful degradation: if Neo4j or LLM is down, SQL/FTS search still works |

### 4.4 Usability & accessibility
| ID | Requirement |
|----|-------------|
| NFR-U1 | UI in English and Tamil; language switch persists |
| NFR-U2 | Mobile-first responsive layout |
| NFR-U3 | WCAG 2.1 AA targets: contrast, keyboard navigation, labels, alt text |
| NFR-U4 | Plain-language answers (target reading level ≈ grade 8) |
| NFR-U5 | Tamil font support (Noto Sans Tamil) |

### 4.5 Maintainability & quality
| ID | Requirement |
|----|-------------|
| NFR-M1 | Unit-test coverage ≥ 70% overall, ≥ 90% on rules/eligibility/policy/routing modules |
| NFR-M2 | Linting/formatting: ruff + black (Python), eslint + prettier (TS) |
| NFR-M3 | Type checking: mypy (core modules), `tsc --noEmit` |
| NFR-M4 | CI runs lint, type check, tests, migration check on every PR |
| NFR-M5 | OpenAPI documentation generated and kept current |

### 4.6 Explainability & AI quality
| ID | Requirement |
|----|-------------|
| NFR-A1 | Offline evaluation suites: intent, entity, category, routing, eligibility, RAG faithfulness, Tamil |
| NFR-A2 | Faithfulness (answer supported by cited context) ≥ 90% on eval set |
| NFR-A3 | Prompts and model names versioned and stored on each decision |
| NFR-A4 | A fixed "golden question" regression set runs in CI (LLM mocked or pinned) |

## 5. Data requirements

### 5.1 Source tiers
| Tier | Description | Examples (verify availability and licence before use) | Default reliability |
|------|-------------|--------------------------------------------------------|---------------------|
| 1 Official | Government-published | TN OGD, TN IT Dept (e-Sevai, GOs), India Code, MyScheme, IGOD, district portals, TNGIS | 0.95–1.00 |
| 2 Trusted open | Community/derived | Hugging Face scheme/DIPR/facility datasets, GitHub scheme dumps, OSM-derived | 0.70–0.90 |
| 3 Synthetic | Generated by the team | citizens, officers, complaints, evidence | n/a |

> The reliability numbers are the project's own design scores, not official ratings. Dataset names, sizes and URLs listed in the blueprint were taken from the team's research and **must be re-verified** (existence, current counts, licence) at ingestion time and recorded in `source_registry` / `dataset_registry`.

### 5.2 MVP data volumes
| Entity | Target |
|--------|--------|
| Departments | 10–15 (expand to ~49) |
| Districts | All Tamil Nadu |
| Schemes | 30–50 with **manually reviewed** eligibility rules |
| Services | 20–30 |
| Policies | 10–20 |
| GOs / notices | 50+ |
| Laws / rules | 10–20 |
| Facilities | 100–500 |
| Complaint categories | 20–30 |
| Synthetic citizens | 100 |
| Synthetic complaints | 300–1000 |

### 5.3 Data rules
- Raw data is never edited; cleaning produces new artefacts.
- Every production row has `source_id`; scheme/service rows have `verified_at`.
- Eligibility rules for seeded schemes are authored/reviewed by a human and cite the source clause.
- Synthetic data is flagged and distributable (no real names/phones).

### 5.4 Eligibility attribute registry (initial)
`age`, `gender`, `annual_income`, `social_category`, `disability_status`, `bpl_status`, `residence_type`, `district_id`, `state`, `is_student`, `occupation`, `education_level`, `marital_status`, `family_size`, `held_documents`.
Each attribute declares: type, allowed operators, unit, and how to derive it (e.g., `age` from `date_of_birth` as of the evaluation date).

## 6. External interfaces
| Interface | Purpose | Notes |
|-----------|---------|-------|
| LLM provider API | Explanation, extraction proposals | Pluggable; configurable; retry/backoff; no PII by default |
| Embedding model | Multilingual embeddings (1024-d) | Local (sentence-transformers) preferred for cost and privacy |
| STT/TTS | Voice | Provider abstraction; Tamil support to be validated |
| Map tiles | MapLibre/Leaflet | OSM-compatible tiles; respect usage policy |
| Object storage | Evidence/PDFs | MinIO locally |
| Email/SMS | Notifications | Mock in prototype |

## 7. Constraints and assumptions
- Team of 3; ~4 weeks; academic scope.
- Local Docker deployment is sufficient; cloud optional.
- No access to real government back-ends or citizen records.
- Ward-level boundary availability is uncertain; district and taluk are the guaranteed levels.
- LLM cost must be bounded: caching, context truncation and small-model defaults.

## 8. Acceptance criteria (system level)
1. `docker compose up` starts all services; `make seed` loads seed data; `make test` passes.
2. The demo script (see Build Instructions §Demo) runs without manual DB edits.
3. Eligibility gold set (≥ 40 cases) passes at ≥ 95%.
4. Routing test set (≥ 100 synthetic complaints) meets ≥ 90% authority accuracy.
5. Ten golden questions return cited answers; five adversarial questions result in abstention or safe refusal.
6. Overdue complaints in test data escalate automatically; history and escalation rows exist.
7. Every AI answer has a `decision` and ≥ 1 `decision_lineage` row (or `abstained = true`).
8. Audit log contains entries for create/update actions on complaints, schemes, users.

## 9. Traceability
Requirements trace: PRD feature → SRS requirement → table(s) → API → test. Maintain this matrix in `docs/traceability.csv` (see Project Control).
