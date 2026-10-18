# MyGovt — Flow Document

All diagrams are Mermaid (render in GitHub, VS Code with a Mermaid extension, or mermaid.live).
Thresholds shown (0.60, 0.70) are configuration defaults, not fixed constants.

---

## 1. System context

```mermaid
flowchart TB
    C[Citizen<br/>web / mobile / voice] --> FE[Next.js frontend<br/>Tamil + English]
    O[Officer / Admin] --> FE
    FE --> GW[FastAPI gateway<br/>auth · RBAC · rate limit]
    GW --> APP[Application services<br/>schemes · services · complaints · documents · policies]
    GW --> AI[AI orchestration<br/>LangGraph]
    AI --> RET[Retrieval layer<br/>SQL · FTS · vector · graph]
    APP --> PG[(PostgreSQL<br/>system of record)]
    RET --> PG
    PG --- POSTGIS[PostGIS]
    PG --- PGV[pgvector]
    RET --> NEO[(Neo4j<br/>derived graph)]
    APP --> OBJ[(MinIO<br/>evidence · PDFs)]
    GW --> REDIS[(Redis)]
    ETL[ETL pipeline] --> PG
    ETL --> NEO
    SRC[Official · open · synthetic sources] --> ETL
```

## 2. Core principle: answer pipeline

```mermaid
flowchart LR
    Q[Question] --> I[Intent + entities + language]
    I --> R[Hybrid retrieval<br/>hard filters first]
    R --> RU[Rules / policy resolver<br/>deterministic]
    RU --> T[Trust layer]
    T -->|pass| L[LLM explanation<br/>verified context only]
    T -->|fail| AB[Abstain + official link]
    L --> G[Actionability gate]
    AB --> G
    G --> A1[Inform]
    G --> A2[Guide]
    G --> A3[Act via backend API]
    A1 --> D[Decision + lineage]
    A2 --> D
    A3 --> D
    D --> AU[Audit log]
```

## 3. "Ask MyGovt" detailed sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as Citizen
    participant FE as Frontend
    participant API as FastAPI
    participant OR as LangGraph orchestrator
    participant NLP as NLP (intent/entities)
    participant RT as Retriever
    participant DB as PostgreSQL/pgvector/PostGIS
    participant KG as Neo4j
    participant RE as Rule & policy engine
    participant TR as Trust engine
    participant LLM as LLM
    U->>FE: Question (text/voice)
    FE->>API: POST /ai/chat (JWT)
    API->>OR: request + user context
    OR->>NLP: detect language, intent, entities
    NLP-->>OR: intent, entities, confidence
    alt intent = out_of_scope or low confidence
        OR-->>API: clarify / refuse safely
    else
        OR->>RT: query + filters (date, jurisdiction)
        RT->>DB: SQL + FTS + vector candidates
        RT->>KG: graph paths (optional)
        RT-->>OR: scored candidates
        OR->>RE: apply eligibility / policy validity
        RE-->>OR: deterministic results
        OR->>TR: verify candidates + results
        TR-->>OR: trust breakdown + accepted context
        alt trust < threshold or no evidence
            OR-->>API: abstain message + official link
        else
            OR->>LLM: prompt (verified context only)
            LLM-->>OR: answer with citation markers
            OR->>OR: validate citations map to context
        end
        OR->>DB: store decision + lineage + retrieval log
    end
    API-->>FE: answer, citations, trust, action
    FE-->>U: Render + "Why this answer?"
```

## 4. Intent routing

```mermaid
flowchart TD
    S[Start] --> L{Language detect}
    L --> IC[Intent classifier]
    IC -->|scheme_discovery / eligibility_check| E1[Scheme flow §5]
    IC -->|service_info| E2[Service flow §6]
    IC -->|document_search / policy_query| E3[Document & policy flow §7]
    IC -->|complaint| E4[Complaint flow §8]
    IC -->|complaint_status| E5[Lookup by reference → timeline]
    IC -->|greeting| E6[Greeting + capabilities]
    IC -->|out_of_scope e.g. weather, emergency| E7[Polite refusal + pointer to official channels]
    IC -->|confidence < 0.5| E8[Ask one clarifying question]
```

## 5. Scheme discovery and eligibility

```mermaid
flowchart TD
    A[Question or profile form] --> B["Extract attributes: age, gender, income, category, district"]
    B --> C[Merge with stored profile<br/>only if consent given]
    C --> D[PostGIS / graph: resolve district hierarchy]
    D --> E[SQL pre-filter<br/>active · effective dates · level/state]
    E --> F[Semantic + keyword ranking for relevance]
    F --> G[Eligibility engine<br/>deterministic]
    G --> H{Result per scheme}
    H -->|all mandatory rules pass| I[ELIGIBLE]
    H -->|a rule fails| J[NOT_ELIGIBLE<br/>+ failing rule + value]
    H -->|attribute missing| K[INSUFFICIENT_DATA<br/>+ missing list]
    I --> L[Trust layer]
    J --> L
    K --> L
    L --> M[LLM writes explanation<br/>benefits · documents · how to apply]
    M --> N[Save decision + lineage]
```

**Eligibility evaluation algorithm**
```mermaid
flowchart TD
    R0[Load active rules for scheme on evaluation date] --> R1[Group by rule_group]
    R1 --> R2[For each group: evaluate every rule]
    R2 --> R3{Attribute present?}
    R3 -->|no| U[UNKNOWN]
    R3 -->|yes| R4[Apply operator → PASS / FAIL]
    U --> R5
    R4 --> R5["Group result: any FAIL → FAIL; else any UNKNOWN → UNKNOWN; else PASS"]
    R5 --> R6["Across groups (OR): any PASS → ELIGIBLE; else any UNKNOWN → INSUFFICIENT_DATA; else NOT_ELIGIBLE"]
```

## 6. Service discovery and actionability

```mermaid
flowchart TD
    Q[User message] --> I{Intent}
    I -->|"What is an income certificate?"| INF[Information response]
    I -->|"I want to apply for an income certificate"| GUIDE[Guide]
    GUIDE --> S1[Identify service in services.service]
    S1 --> S2[Fee · charge · processing time]
    S2 --> S3[Required documents + which the user holds]
    S3 --> S4[Official application link]
    I -->|"Garbage dumped on my street"| ACT[Complaint detected → Complaint flow §8]
```

## 7. Document and policy search with policy resolver

```mermaid
flowchart TD
    Q[Query + query date + jurisdiction] --> H[Hard filters<br/>status · effective_date ≤ date < expiry · jurisdiction]
    H --> K[Keyword FTS + trigram]
    H --> V[Vector search]
    K --> M[Merge + normalise scores]
    V --> M
    M --> P{Policy topic?}
    P -->|yes| PV[Policy resolver: pick the single version valid on date]
    P -->|no| RR[Re-rank: + reliability + freshness + graph]
    PV --> RR
    RR --> TL[Trust layer] --> CTX[Context builder + citation manager]
```

## 8. Complaint lifecycle

```mermaid
flowchart TD
    A[Citizen text/voice + optional evidence + location] --> B[STT if voice]
    B --> C[Language detect]
    C --> D[Classify: category · priority · sentiment]
    D --> E{Confidence ≥ 0.60?}
    E -->|no| TQ[Status: needs_triage → human triage queue]
    E -->|yes| F[Resolve location → PostGIS jurisdiction]
    F --> G{Inside Tamil Nadu?}
    G -->|no| X[Ask for a valid location]
    G -->|yes| H[routing_rule lookup<br/>category × jurisdiction level]
    H --> I[Authority + department]
    I --> J[Officer assignment<br/>round-robin / least-loaded]
    J --> K[sla_rule → due_date, escalation_due_at]
    K --> L[Create complaint MYG-YYYY-NNNNNN<br/>history row · audit row]
    L --> M[Notify citizen + officer]
    TQ --> N[Triager sets category] --> F
```

**Status state machine**
```mermaid
stateDiagram-v2
    [*] --> submitted
    submitted --> needs_triage: low confidence
    submitted --> classified
    needs_triage --> classified: triager decision
    classified --> assigned
    assigned --> in_progress: officer accepts
    in_progress --> resolved
    resolved --> closed: citizen confirms / auto-close after N days
    resolved --> reopened: citizen disputes
    reopened --> in_progress
    assigned --> escalated: SLA breach
    in_progress --> escalated: SLA breach
    escalated --> in_progress: higher authority acts
    submitted --> rejected: invalid / duplicate
    closed --> [*]
    rejected --> [*]
```

## 9. SLA monitoring and escalation

```mermaid
sequenceDiagram
    participant SCH as Scheduler (every 5 min)
    participant DB as PostgreSQL
    participant ESC as Escalation service
    participant N as Notifier
    SCH->>DB: SELECT complaints WHERE escalation_due_at < now AND no open escalation
    loop each complaint
        SCH->>ESC: escalate(complaint_id)
        ESC->>DB: BEGIN; lock row (FOR UPDATE SKIP LOCKED)
        ESC->>DB: parent_authority_id of current authority
        alt parent exists
            ESC->>DB: INSERT escalation; UPDATE complaint (authority, status=escalated, new escalation_due_at); history; audit
            ESC->>N: notify parent authority + citizen
        else top of chain
            ESC->>DB: flag "unresolved at top level"; notify state admin
        end
        ESC->>DB: COMMIT
    end
```
Idempotency: the `NOT EXISTS open escalation` check plus row lock means re-runs do nothing twice.

## 10. Jurisdiction resolution

```mermaid
flowchart LR
    P[lat, lon] --> V{Valid & inside TN bbox?}
    V -->|no| E[Error: unsupported area]
    V -->|yes| W[ST_Contains ward]
    W -->|hit| LB[local body]
    W -->|miss| LB2[ST_Contains local_body]
    LB --> T[taluk] --> D[district] --> AU[authority via routing rule]
    LB2 --> T
    LB2 -->|miss| T2[ST_Contains taluk] --> D
    T2 -->|miss| D2[ST_Contains district] --> AU
```
Fallback behaviour: if the finest level is unavailable (no ward polygons), route at the finest resolved level and record that level on the decision.

## 11. Data ingestion (ETL)

```mermaid
flowchart TD
    A[Register source in source_registry<br/>licence · reliability] --> B[Download]
    B --> C[SHA-256 checksum]
    C --> D{Already loaded?}
    D -->|yes| Z[Skip]
    D -->|no| E[Store in data/raw — immutable]
    E --> F[Extract: CSV · JSON · API · PDF · HTML · GIS]
    F --> G[Profile]
    G --> H[Clean · normalise · dedupe]
    H --> I[Validate schema · ranges · vocab · FKs]
    I -->|fail| Q[Quarantine + reason]
    I -->|pass| J[Staging tables]
    J --> K[Source verification + quality score]
    K --> L[Upsert to production, idempotent]
    L --> M[Chunk + embed documents]
    L --> N[Rebuild/refresh Neo4j projection]
    M --> O[HNSW + FTS indexes]
```

## 12. Knowledge graph build and use

```mermaid
flowchart LR
    PG[(PostgreSQL)] --> EX[Export nodes + relationships]
    EX --> NEO[(Neo4j)]
    NEO --> Q1["Citizen district → schemes available"]
    NEO --> Q2["Scheme → required documents → issuing service"]
    NEO --> Q3["Authority → escalation chain"]
    Q1 --> RET[Retriever]
    Q2 --> RET
    Q3 --> RET
```

## 13. Authentication and authorisation

```mermaid
sequenceDiagram
    actor U as User
    participant API as FastAPI
    participant DB as PostgreSQL
    U->>API: POST /auth/login
    API->>DB: verify hash, status, lockout
    API-->>U: access JWT (15 min) + refresh token
    U->>API: request + Bearer JWT
    API->>API: verify signature, expiry, role
    API->>DB: BEGIN; SET LOCAL app.role, app.citizen_id
    API->>DB: query (RLS + service-layer jurisdiction filter)
    API->>DB: audit_log insert
    API-->>U: response
```

## 14. Voice flow

```mermaid
flowchart LR
    M[Mic] --> STT[Speech-to-text]
    STT --> LD[Language detect: ta / en / Tanglish]
    LD --> PIPE[Same pipeline as text — §3 or §8]
    PIPE --> TXT[Answer text]
    TXT --> TTS[Text-to-speech in user's language]
    TTS --> SP[Speaker]
    STT -.->|confidence low| CONF[Show transcript for confirmation before submitting a complaint]
```

## 15. Officer and admin flows

```mermaid
flowchart TD
    O[Officer login] --> Q[Queue sorted by SLA risk]
    Q --> V[Open complaint: details · map · evidence · history]
    V --> ACC[Accept] --> WIP[In progress + note]
    WIP --> RES[Resolve + citizen-visible note]
    V --> REA[Request reassignment] --> DA[Dept admin]
    DA --> DASH[Dashboard: counts · SLA · heatmap · performance]
    SA[State/system admin] --> MASTER[Departments · authorities · sources · datasets · AI decisions · audit]
```

## 16. Deployment topology (local / demo)

```mermaid
flowchart LR
    subgraph Docker Compose
      FE[frontend :3000] --> BE[backend :8000]
      BE --> PG[(postgres+postgis+pgvector :5432)]
      BE --> N4J[(neo4j :7687)]
      BE --> RD[(redis :6379)]
      BE --> MN[(minio :9000)]
      WK[worker + scheduler] --> PG
      WK --> N4J
      ETL[etl job] --> PG
    end
    BE --> LLM[(LLM API)]
```

## 17. Error and fallback handling

| Failure | Behaviour |
|---------|-----------|
| LLM down/timeout | Return structured results (schemes/rules/citations) without prose; mark `degraded=true` |
| Neo4j down | Skip graph term; use SQL/vector only |
| Embedding service down | Keyword + SQL only |
| STT low confidence | Ask the user to confirm transcript |
| No coordinates | Ask for map pin/address; allow district-level submission |
| Trust below threshold | Abstain; link to official source |
| Classifier low confidence | Triage queue |
| Duplicate upload | Reject by hash |
