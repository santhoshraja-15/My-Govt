-- =====================================================================
-- MyGovt — PostgreSQL schema  (PostgreSQL 16 + PostGIS 3 + pgvector 0.7+)
-- Run order: this single file is idempotent-safe on an EMPTY database.
-- Embedding dimension is 1024 (e.g. BAAI/bge-m3, multilingual-e5-large).
-- If you change the embedding model, change vector(1024) everywhere.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- exclusion constraints on policy versions

CREATE SCHEMA IF NOT EXISTS system;
CREATE SCHEMA IF NOT EXISTS administration;
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS schemes;
CREATE SCHEMA IF NOT EXISTS services;
CREATE SCHEMA IF NOT EXISTS policies;
CREATE SCHEMA IF NOT EXISTS documents;
CREATE SCHEMA IF NOT EXISTS complaints;
CREATE SCHEMA IF NOT EXISTS ai;
CREATE SCHEMA IF NOT EXISTS audit;

-- ---------------------------------------------------------------------
-- Generic helpers
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION system.touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$ LANGUAGE plpgsql;

-- =====================================================================
-- SYSTEM: source & dataset registry (data lineage root)
-- =====================================================================
CREATE TABLE system.source_registry (
  source_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code        text UNIQUE NOT NULL,                 -- e.g. SRC001
  source_name        text NOT NULL,
  department         text,
  source_type        text NOT NULL CHECK (source_type IN ('official','trusted_open','synthetic')),
  url                text,
  format             text,                                  -- CSV/JSON/API/PDF/HTML/GIS
  jurisdiction       text,
  access_method      text,
  reliability_score  numeric(3,2) CHECK (reliability_score BETWEEN 0 AND 1),
  update_frequency   text,
  license            text,
  last_checked       timestamptz,
  last_updated       timestamptz,
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','deprecated','blocked')),
  notes              text
);

CREATE TABLE system.dataset_registry (
  dataset_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_name       text NOT NULL,
  source_id          uuid NOT NULL REFERENCES system.source_registry(source_id),
  file_name          text,
  file_format        text,
  download_date      timestamptz,
  record_count       integer,
  version            text,
  checksum_sha256    text,
  processing_status  text NOT NULL DEFAULT 'raw'
                     CHECK (processing_status IN ('raw','extracted','cleaned','validated','loaded','quarantined')),
  validation_status  text,
  quality_completeness numeric(5,2),
  quality_accuracy     numeric(5,2),
  quality_consistency  numeric(5,2),
  quality_freshness    numeric(5,2),
  notes              text,
  UNIQUE (source_id, checksum_sha256)
);

CREATE TABLE system.quarantine_record (
  quarantine_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id     uuid NOT NULL REFERENCES system.dataset_registry(dataset_id),
  raw_payload    jsonb NOT NULL,
  failure_reason text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  resolved       boolean NOT NULL DEFAULT false
);

CREATE TABLE system.feature_flag (
  flag_key text PRIMARY KEY,
  enabled  boolean NOT NULL DEFAULT false,
  notes    text
);

-- =====================================================================
-- ADMINISTRATION: geography, departments, authorities, officers
-- =====================================================================
CREATE TABLE administration.state (
  state_id   serial PRIMARY KEY,
  state_code text UNIQUE NOT NULL,
  state_name text NOT NULL
);

CREATE TABLE administration.district (
  district_id   serial PRIMARY KEY,
  state_id      int NOT NULL REFERENCES administration.state(state_id),
  district_code text UNIQUE NOT NULL,
  district_name text NOT NULL,
  name_ta       text,
  geometry      geometry(MultiPolygon,4326)
);

CREATE TABLE administration.revenue_division (
  division_id serial PRIMARY KEY,
  district_id int NOT NULL REFERENCES administration.district(district_id),
  name        text NOT NULL,
  geometry    geometry(MultiPolygon,4326)
);

CREATE TABLE administration.taluk (
  taluk_id    serial PRIMARY KEY,
  district_id int NOT NULL REFERENCES administration.district(district_id),
  division_id int REFERENCES administration.revenue_division(division_id),
  name        text NOT NULL,
  name_ta     text,
  geometry    geometry(MultiPolygon,4326)
);

CREATE TABLE administration.block (
  block_id    serial PRIMARY KEY,
  district_id int NOT NULL REFERENCES administration.district(district_id),
  name        text NOT NULL,
  geometry    geometry(MultiPolygon,4326)
);

CREATE TABLE administration.local_body (
  local_body_id serial PRIMARY KEY,
  district_id   int NOT NULL REFERENCES administration.district(district_id),
  taluk_id      int REFERENCES administration.taluk(taluk_id),
  type          text NOT NULL CHECK (type IN ('corporation','municipality','town_panchayat','village_panchayat','panchayat_union')),
  name          text NOT NULL,
  name_ta       text,
  geometry      geometry(MultiPolygon,4326)
);

CREATE TABLE administration.ward (
  ward_id       serial PRIMARY KEY,
  local_body_id int NOT NULL REFERENCES administration.local_body(local_body_id),
  ward_number   text NOT NULL,
  geometry      geometry(MultiPolygon,4326),
  UNIQUE (local_body_id, ward_number)
);

CREATE TABLE administration.department (
  department_id   serial PRIMARY KEY,
  department_code text UNIQUE NOT NULL,
  department_name text NOT NULL,
  name_ta         text,
  description     text,
  website_url     text,
  contact_email   text,
  contact_phone   text,
  status          text NOT NULL DEFAULT 'active',
  source_id       uuid REFERENCES system.source_registry(source_id)
);

CREATE TABLE administration.department_hierarchy (
  hierarchy_id         serial PRIMARY KEY,
  parent_department_id int NOT NULL REFERENCES administration.department(department_id),
  child_department_id  int NOT NULL REFERENCES administration.department(department_id),
  relationship_type    text NOT NULL DEFAULT 'parent_of',
  CHECK (parent_department_id <> child_department_id),
  UNIQUE (parent_department_id, child_department_id)
);

CREATE TABLE administration.authority (
  authority_id       serial PRIMARY KEY,
  department_id      int NOT NULL REFERENCES administration.department(department_id),
  authority_type     text NOT NULL CHECK (authority_type IN ('state','district','taluk','municipal','panchayat','department_office')),
  authority_name     text NOT NULL,
  jurisdiction_level text NOT NULL CHECK (jurisdiction_level IN ('state','district','taluk','local_body','ward')),
  jurisdiction_id    int,                       -- id in the table implied by jurisdiction_level
  parent_authority_id int REFERENCES administration.authority(authority_id), -- escalation chain
  contact_information jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE administration.officer (            -- SYNTHETIC DATA ONLY in prototype
  officer_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  department_id int NOT NULL REFERENCES administration.department(department_id),
  authority_id  int NOT NULL REFERENCES administration.authority(authority_id),
  name          text NOT NULL,
  designation   text NOT NULL,
  employee_code text UNIQUE,
  email         text,
  phone         text,
  status        text NOT NULL DEFAULT 'active'
);

-- =====================================================================
-- IDENTITY
-- =====================================================================
CREATE TABLE identity.app_user (
  user_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email          text UNIQUE,
  phone          text UNIQUE,
  password_hash  text NOT NULL,                 -- argon2id / bcrypt
  role           text NOT NULL CHECK (role IN
                 ('citizen','officer','department_admin','state_admin','system_admin','ai_readonly','etl_user')),
  officer_id     uuid REFERENCES administration.officer(officer_id),
  status         text NOT NULL DEFAULT 'active',
  failed_logins  int NOT NULL DEFAULT 0,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_app_user_touch BEFORE UPDATE ON identity.app_user
  FOR EACH ROW EXECUTE FUNCTION system.touch_updated_at();

CREATE TABLE identity.citizen (                  -- SYNTHETIC DATA ONLY in prototype
  citizen_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid UNIQUE REFERENCES identity.app_user(user_id),
  name               text NOT NULL,
  preferred_language text NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en','ta','tanglish')),
  status             text NOT NULL DEFAULT 'active',
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_citizen_touch BEFORE UPDATE ON identity.citizen
  FOR EACH ROW EXECUTE FUNCTION system.touch_updated_at();

-- NOTE: Never store Aadhaar numbers. Store only the *type* of documents a citizen holds.
CREATE TABLE identity.citizen_profile (
  profile_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id      uuid UNIQUE NOT NULL REFERENCES identity.citizen(citizen_id) ON DELETE CASCADE,
  date_of_birth   date,
  gender          text CHECK (gender IN ('female','male','transgender','other','undisclosed')),
  occupation      text,
  is_student      boolean,
  annual_income   numeric(12,2),
  social_category text,                         -- OC/BC/MBC/SC/ST etc. (as per scheme vocabulary)
  disability_status boolean,
  bpl_status      boolean,
  residence_type  text CHECK (residence_type IN ('rural','urban')),
  district_id     int REFERENCES administration.district(district_id),
  taluk_id        int REFERENCES administration.taluk(taluk_id),
  local_body_id   int REFERENCES administration.local_body(local_body_id),
  held_documents  text[] NOT NULL DEFAULT '{}',
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.consent (
  consent_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id  uuid NOT NULL REFERENCES identity.citizen(citizen_id) ON DELETE CASCADE,
  purpose     text NOT NULL,                    -- e.g. 'profile_based_scheme_matching'
  granted     boolean NOT NULL,
  granted_at  timestamptz NOT NULL DEFAULT now(),
  revoked_at  timestamptz
);

-- =====================================================================
-- DOCUMENTS (needed before schemes/policies reference them)
-- =====================================================================
CREATE TABLE documents.document (
  document_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title            text NOT NULL,
  document_type    text NOT NULL CHECK (document_type IN
                   ('GO','Gazette','Notice','Circular','Policy','Law','Rule','Scheme','Announcement','Guideline','Manual')),
  department_id    int REFERENCES administration.department(department_id),
  source_id        uuid REFERENCES system.source_registry(source_id),
  dataset_id       uuid REFERENCES system.dataset_registry(dataset_id),
  source_url       text,
  file_path        text,
  file_hash        text,
  language         text CHECK (language IN ('en','ta','mixed')),
  publication_date date,
  effective_date   date,
  expiry_date      date,
  jurisdiction_level text DEFAULT 'state',
  jurisdiction_id  int,
  version          text,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','withdrawn','draft')),
  full_text        text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (file_hash)
);
CREATE INDEX idx_document_type_date ON documents.document (document_type, publication_date DESC);
CREATE INDEX idx_document_dept      ON documents.document (department_id);

CREATE TABLE documents.document_chunk (
  chunk_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid NOT NULL REFERENCES documents.document(document_id) ON DELETE CASCADE,
  chunk_number  int NOT NULL,
  content       text NOT NULL,
  page_number   int,
  section_title text,
  language      text,
  embedding     vector(1024),
  metadata      jsonb NOT NULL DEFAULT '{}',
  tsv           tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(section_title,'') || ' ' || content)) STORED,
  UNIQUE (document_id, chunk_number)
);
CREATE INDEX idx_chunk_tsv  ON documents.document_chunk USING GIN (tsv);
CREATE INDEX idx_chunk_trgm ON documents.document_chunk USING GIN (content gin_trgm_ops);
CREATE INDEX idx_chunk_vec  ON documents.document_chunk USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- =====================================================================
-- POLICIES / LAWS / GOs  (versioned, never overwritten)
-- =====================================================================
CREATE TABLE policies.law (
  law_id       serial PRIMARY KEY,
  law_name     text NOT NULL,
  act_number   text,
  year         int,
  description  text,
  official_url text,
  source_id    uuid REFERENCES system.source_registry(source_id)
);

CREATE TABLE policies.rule (
  rule_id        serial PRIMARY KEY,
  law_id         int NOT NULL REFERENCES policies.law(law_id),
  rule_name      text NOT NULL,
  description    text,
  effective_from date,
  effective_to   date,
  document_id    uuid REFERENCES documents.document(document_id)
);

CREATE TABLE policies.policy (
  policy_id     serial PRIMARY KEY,
  policy_name   text NOT NULL,
  policy_type   text NOT NULL,
  department_id int REFERENCES administration.department(department_id),
  description   text,
  official_url  text,
  jurisdiction_level text NOT NULL DEFAULT 'state',
  jurisdiction_id    int,
  status        text NOT NULL DEFAULT 'active'
);

CREATE TABLE policies.policy_version (
  policy_version_id serial PRIMARY KEY,
  policy_id      int NOT NULL REFERENCES policies.policy(policy_id),
  version_number int NOT NULL,
  effective_from date NOT NULL,
  effective_to   date,                           -- NULL = open-ended
  document_id    uuid REFERENCES documents.document(document_id),
  change_summary text,
  content_hash   text,
  UNIQUE (policy_id, version_number),
  -- no two versions of the same policy may be effective at the same time
  EXCLUDE USING gist (policy_id WITH =,
                      daterange(effective_from, effective_to, '[)') WITH &&)
);

CREATE TABLE policies.government_order (
  go_id          serial PRIMARY KEY,
  go_number      text NOT NULL,
  title          text NOT NULL,
  department_id  int REFERENCES administration.department(department_id),
  order_date     date,
  effective_date date,
  document_id    uuid REFERENCES documents.document(document_id),
  status         text NOT NULL DEFAULT 'active',
  summary        text,
  keywords       text[],
  UNIQUE (go_number, department_id, order_date)
);

-- =====================================================================
-- SCHEMES
-- =====================================================================
CREATE TABLE schemes.scheme (
  scheme_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheme_code      text UNIQUE NOT NULL,
  scheme_name      text NOT NULL,
  name_ta          text,
  short_description text,
  full_description text,
  scheme_level     text NOT NULL CHECK (scheme_level IN ('central','state','district')),
  department_id    int REFERENCES administration.department(department_id),
  state_id         int REFERENCES administration.state(state_id),
  category         text,
  benefits_summary text,
  application_url  text,
  official_url     text,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','closed','suspended','draft')),
  effective_from   date,
  effective_to     date,
  policy_version_id int REFERENCES policies.policy_version(policy_version_id),
  source_id        uuid REFERENCES system.source_registry(source_id),
  dataset_id       uuid REFERENCES system.dataset_registry(dataset_id),
  verified_at      timestamptz,                  -- last verified against an official source
  embedding        vector(1024),
  tsv              tsvector,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_scheme_touch BEFORE UPDATE ON schemes.scheme
  FOR EACH ROW EXECUTE FUNCTION system.touch_updated_at();
CREATE INDEX idx_scheme_department ON schemes.scheme (department_id);
CREATE INDEX idx_scheme_category   ON schemes.scheme (category);
CREATE INDEX idx_scheme_status     ON schemes.scheme (status);
CREATE INDEX idx_scheme_tsv        ON schemes.scheme USING GIN (tsv);
CREATE INDEX idx_scheme_vec        ON schemes.scheme USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION schemes.refresh_tsv() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple',
    coalesce(NEW.scheme_name,'')||' '||coalesce(NEW.name_ta,'')||' '||
    coalesce(NEW.short_description,'')||' '||coalesce(NEW.benefits_summary,'')||' '||coalesce(NEW.category,''));
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_scheme_tsv BEFORE INSERT OR UPDATE ON schemes.scheme
  FOR EACH ROW EXECUTE FUNCTION schemes.refresh_tsv();

CREATE TABLE schemes.eligibility_rule (
  rule_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheme_id      uuid NOT NULL REFERENCES schemes.scheme(scheme_id) ON DELETE CASCADE,
  rule_group     int NOT NULL DEFAULT 1,         -- rules in same group = AND; groups = OR
  rule_type      text NOT NULL DEFAULT 'demographic',
  attribute      text NOT NULL,                  -- must exist in the profile attribute registry
  operator       text NOT NULL CHECK (operator IN ('=','!=','>','>=','<','<=','IN','NOT_IN','BETWEEN','IS_TRUE','IS_FALSE')),
  value          jsonb NOT NULL,                 -- scalar | array | [lo,hi]
  unit           text,
  mandatory      boolean NOT NULL DEFAULT true,
  priority       int NOT NULL DEFAULT 100,
  human_readable text,                           -- shown to the citizen (en)
  human_readable_ta text,
  source_reference text,                         -- clause/para in the official doc
  effective_from date,
  effective_to   date
);
CREATE INDEX idx_elig_scheme ON schemes.eligibility_rule (scheme_id);

CREATE TABLE schemes.benefit (
  benefit_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheme_id    uuid NOT NULL REFERENCES schemes.scheme(scheme_id) ON DELETE CASCADE,
  benefit_type text NOT NULL,                    -- cash, in_kind, subsidy, scholarship, loan...
  description  text,
  amount       numeric(14,2),
  currency     text DEFAULT 'INR',
  frequency    text,                             -- one_time, monthly, annual...
  conditions   text
);

CREATE TABLE schemes.document_requirement (
  document_requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheme_id        uuid NOT NULL REFERENCES schemes.scheme(scheme_id) ON DELETE CASCADE,
  document_name    text NOT NULL,
  document_code    text,                         -- normalised, links to services.service where obtainable
  mandatory        boolean NOT NULL DEFAULT true,
  description      text,
  issuing_authority text
);

-- =====================================================================
-- SERVICES (e-Sevai etc.)
-- =====================================================================
CREATE TABLE services.service (
  service_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_code    text,
  service_name    text NOT NULL,
  name_ta         text,
  department_id   int REFERENCES administration.department(department_id),
  category        text,
  description     text,
  service_type    text,
  application_url text,
  official_url    text,
  government_fee  numeric(10,2),
  service_charge  numeric(10,2),
  processing_time text,
  status          text NOT NULL DEFAULT 'active',
  source_id       uuid REFERENCES system.source_registry(source_id),
  verified_at     timestamptz,
  embedding       vector(1024),
  tsv             tsvector,
  UNIQUE (service_code, department_id)
);
CREATE INDEX idx_service_department ON services.service (department_id);
CREATE INDEX idx_service_tsv        ON services.service USING GIN (tsv);
CREATE INDEX idx_service_vec        ON services.service USING hnsw (embedding vector_cosine_ops);

CREATE TABLE services.service_requirement (
  requirement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_id     uuid NOT NULL REFERENCES services.service(service_id) ON DELETE CASCADE,
  document_name  text NOT NULL,
  mandatory      boolean NOT NULL DEFAULT true,
  description    text
);

CREATE TABLE services.government_facility (
  facility_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  facility_type text,
  district_id   int REFERENCES administration.district(district_id),
  pin_code      text,
  operator      text,
  opening_hours text,
  location      geometry(Point,4326),
  source_id     uuid REFERENCES system.source_registry(source_id)   -- OSM-derived => lower reliability
);
CREATE INDEX idx_facility_geom ON services.government_facility USING GIST (location);

-- =====================================================================
-- COMPLAINTS
-- =====================================================================
CREATE TABLE complaints.complaint_category (
  category_id          serial PRIMARY KEY,
  category_code        text UNIQUE NOT NULL,
  category_name        text NOT NULL,
  name_ta              text,
  description          text,
  default_department_id int REFERENCES administration.department(department_id),
  default_priority     text NOT NULL DEFAULT 'medium' CHECK (default_priority IN ('low','medium','high','critical')),
  default_sla_hours    int NOT NULL DEFAULT 72
);

-- Deterministic routing: (category, jurisdiction level) -> authority type/department
CREATE TABLE complaints.routing_rule (
  routing_rule_id    serial PRIMARY KEY,
  category_id        int NOT NULL REFERENCES complaints.complaint_category(category_id),
  jurisdiction_level text NOT NULL CHECK (jurisdiction_level IN ('state','district','taluk','local_body','ward')),
  local_body_type    text,                       -- optional filter e.g. 'corporation'
  department_id      int NOT NULL REFERENCES administration.department(department_id),
  authority_type     text NOT NULL,
  priority_order     int NOT NULL DEFAULT 1
);

CREATE TABLE complaints.sla_rule (
  sla_id           serial PRIMARY KEY,
  department_id    int REFERENCES administration.department(department_id),
  category_id      int NOT NULL REFERENCES complaints.complaint_category(category_id),
  priority         text NOT NULL CHECK (priority IN ('low','medium','high','critical')),
  resolution_hours int NOT NULL,
  escalation_hours int NOT NULL,
  UNIQUE (department_id, category_id, priority)
);

CREATE SEQUENCE complaints.complaint_seq START 1;

CREATE TABLE complaints.complaint (
  complaint_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_ref       text UNIQUE NOT NULL DEFAULT
                      ('MYG-' || to_char(now(),'YYYY') || '-' || lpad(nextval('complaints.complaint_seq')::text, 6, '0')),
  citizen_id          uuid NOT NULL REFERENCES identity.citizen(citizen_id),
  title               text NOT NULL,
  description         text NOT NULL,
  language            text,
  category_id         int REFERENCES complaints.complaint_category(category_id),
  category_confidence numeric(4,3),
  department_id       int REFERENCES administration.department(department_id),
  authority_id        int REFERENCES administration.authority(authority_id),
  assigned_officer_id uuid REFERENCES administration.officer(officer_id),
  priority            text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high','critical')),
  status              text NOT NULL DEFAULT 'submitted' CHECK (status IN
                      ('submitted','needs_triage','classified','assigned','in_progress','resolved','closed','rejected','escalated','reopened')),
  is_corruption_report boolean NOT NULL DEFAULT false,
  is_anonymous        boolean NOT NULL DEFAULT false,
  latitude            double precision,
  longitude           double precision,
  location            geometry(Point,4326),
  ward_id             int REFERENCES administration.ward(ward_id),
  local_body_id       int REFERENCES administration.local_body(local_body_id),
  taluk_id            int REFERENCES administration.taluk(taluk_id),
  district_id         int REFERENCES administration.district(district_id),
  decision_id         uuid,                      -- FK added after ai.decision exists
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  due_date            timestamptz,
  escalation_due_at   timestamptz,
  resolved_at         timestamptz
);
CREATE TRIGGER trg_complaint_touch BEFORE UPDATE ON complaints.complaint
  FOR EACH ROW EXECUTE FUNCTION system.touch_updated_at();
CREATE INDEX idx_complaint_status     ON complaints.complaint (status);
CREATE INDEX idx_complaint_department ON complaints.complaint (department_id);
CREATE INDEX idx_complaint_created    ON complaints.complaint (created_at);
CREATE INDEX idx_complaint_citizen    ON complaints.complaint (citizen_id);
CREATE INDEX idx_complaint_due        ON complaints.complaint (due_date) WHERE status NOT IN ('resolved','closed','rejected');
CREATE INDEX idx_complaint_geom       ON complaints.complaint USING GIST (location);

CREATE TABLE complaints.complaint_history (
  history_id   bigserial PRIMARY KEY,
  complaint_id uuid NOT NULL REFERENCES complaints.complaint(complaint_id) ON DELETE CASCADE,
  old_status   text,
  new_status   text NOT NULL,
  changed_by   uuid,                             -- app_user.user_id, NULL = system
  remarks      text,
  changed_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_chist_complaint ON complaints.complaint_history (complaint_id, changed_at);

CREATE OR REPLACE FUNCTION complaints.log_status_change() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO complaints.complaint_history(complaint_id, old_status, new_status, remarks)
    VALUES (NEW.complaint_id, NULL, NEW.status, 'created');
  ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO complaints.complaint_history(complaint_id, old_status, new_status)
    VALUES (NEW.complaint_id, OLD.status, NEW.status);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_complaint_history AFTER INSERT OR UPDATE OF status ON complaints.complaint
  FOR EACH ROW EXECUTE FUNCTION complaints.log_status_change();

CREATE TABLE complaints.escalation (
  escalation_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_id      uuid NOT NULL REFERENCES complaints.complaint(complaint_id) ON DELETE CASCADE,
  from_authority_id int REFERENCES administration.authority(authority_id),
  to_authority_id   int NOT NULL REFERENCES administration.authority(authority_id),
  reason            text NOT NULL,
  triggered_at      timestamptz NOT NULL DEFAULT now(),
  resolved_at       timestamptz,
  status            text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved'))
);

CREATE TABLE complaints.evidence (
  evidence_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_id        uuid NOT NULL REFERENCES complaints.complaint(complaint_id) ON DELETE CASCADE,
  evidence_type       text NOT NULL CHECK (evidence_type IN ('image','pdf','video','audio','document')),
  file_path           text NOT NULL,             -- object-storage key
  file_hash           text NOT NULL,
  mime_type           text,
  size_bytes          bigint,
  description         text,
  uploaded_at         timestamptz NOT NULL DEFAULT now(),
  verification_status text NOT NULL DEFAULT 'pending' CHECK (verification_status IN ('pending','verified','rejected'))
);

CREATE TABLE complaints.officer_note (
  note_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  complaint_id uuid NOT NULL REFERENCES complaints.complaint(complaint_id) ON DELETE CASCADE,
  officer_id   uuid NOT NULL REFERENCES administration.officer(officer_id),
  note         text NOT NULL,
  visible_to_citizen boolean NOT NULL DEFAULT false,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- AI: conversations, decisions, lineage, retrieval logs
-- =====================================================================
CREATE TABLE ai.conversation (
  conversation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id      uuid REFERENCES identity.citizen(citizen_id),
  channel         text NOT NULL DEFAULT 'web' CHECK (channel IN ('web','mobile','voice')),
  language        text,
  started_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.message (
  message_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES ai.conversation(conversation_id) ON DELETE CASCADE,
  role            text NOT NULL CHECK (role IN ('user','assistant','system')),
  content         text NOT NULL,
  language        text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.decision (
  decision_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  citizen_id       uuid REFERENCES identity.citizen(citizen_id),
  conversation_id  uuid REFERENCES ai.conversation(conversation_id),
  request_id       text,                          -- correlation id from the API gateway
  decision_type    text NOT NULL CHECK (decision_type IN
                   ('scheme_eligibility','complaint_category','complaint_routing','jurisdiction',
                    'policy_applicability','service_recommendation','information_answer','actionability')),
  result           jsonb NOT NULL,
  confidence_score numeric(4,3),
  trust_breakdown  jsonb,                         -- {source,freshness,jurisdiction,validity,consistency}
  abstained        boolean NOT NULL DEFAULT false,
  model_name       text,
  prompt_version   text,
  rules_version    text,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_decision_citizen ON ai.decision (citizen_id, created_at DESC);
ALTER TABLE complaints.complaint
  ADD CONSTRAINT fk_complaint_decision FOREIGN KEY (decision_id) REFERENCES ai.decision(decision_id);

CREATE TABLE ai.decision_lineage (
  lineage_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id      uuid NOT NULL REFERENCES ai.decision(decision_id) ON DELETE CASCADE,
  source_type      text NOT NULL,                 -- scheme | service | document_chunk | policy_version | rule | profile_attr | graph_path
  source_id        text NOT NULL,
  source_reference text,
  rule_id          uuid,
  evidence_id      uuid,
  policy_version_id int,
  reason           text,
  contribution     text CHECK (contribution IN ('supports','contradicts','neutral')),
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_lineage_decision ON ai.decision_lineage (decision_id);

CREATE TABLE ai.retrieval_log (
  retrieval_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id    uuid REFERENCES ai.decision(decision_id) ON DELETE CASCADE,
  query_text     text NOT NULL,
  keyword_score  numeric, semantic_score numeric, graph_score numeric,
  reliability_score numeric, freshness_score numeric, hybrid_score numeric,
  item_type      text, item_id text,
  accepted       boolean, reject_reason text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.evaluation_run (
  run_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  suite       text NOT NULL,                      -- e.g. 'intent', 'routing', 'eligibility', 'rag_faithfulness'
  metrics     jsonb NOT NULL,
  git_sha     text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- AUDIT (append-only)
-- =====================================================================
CREATE TABLE audit.audit_log (
  audit_id    bigserial PRIMARY KEY,
  user_id     uuid,
  user_role   text,
  action      text NOT NULL,
  entity_type text NOT NULL,
  entity_id   text,
  old_value   jsonb,
  new_value   jsonb,
  ip_address  inet,
  request_id  text,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit.audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_time   ON audit.audit_log (occurred_at);

CREATE OR REPLACE FUNCTION audit.block_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE OR DELETE ON audit.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.block_mutation();

-- =====================================================================
-- GIS: spatial indexes + jurisdiction resolver
-- =====================================================================
CREATE INDEX idx_district_geom ON administration.district USING GIST (geometry);
CREATE INDEX idx_taluk_geom    ON administration.taluk    USING GIST (geometry);
CREATE INDEX idx_block_geom    ON administration.block    USING GIST (geometry);
CREATE INDEX idx_lb_geom       ON administration.local_body USING GIST (geometry);
CREATE INDEX idx_ward_geom     ON administration.ward     USING GIST (geometry);

CREATE OR REPLACE FUNCTION administration.resolve_jurisdiction(p_lon double precision, p_lat double precision)
RETURNS TABLE (ward_id int, local_body_id int, taluk_id int, district_id int) AS $$
  WITH pt AS (SELECT ST_SetSRID(ST_Point(p_lon, p_lat), 4326) AS g)
  SELECT w.ward_id,
         COALESCE(w.local_body_id, lb.local_body_id),
         COALESCE(lb.taluk_id, t.taluk_id),
         COALESCE(t.district_id, d.district_id)
  FROM pt
  LEFT JOIN administration.ward       w  ON ST_Contains(w.geometry,  pt.g)
  LEFT JOIN administration.local_body lb ON ST_Contains(lb.geometry, pt.g)
  LEFT JOIN administration.taluk      t  ON ST_Contains(t.geometry,  pt.g)
  LEFT JOIN administration.district   d  ON ST_Contains(d.geometry,  pt.g)
  LIMIT 1;
$$ LANGUAGE sql STABLE;

-- Auto-fill complaint.location and jurisdiction from lat/lon
CREATE OR REPLACE FUNCTION complaints.fill_location() RETURNS trigger AS $$
DECLARE j record;
BEGIN
  IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
    NEW.location := ST_SetSRID(ST_Point(NEW.longitude, NEW.latitude), 4326);
    SELECT * INTO j FROM administration.resolve_jurisdiction(NEW.longitude, NEW.latitude);
    IF FOUND THEN
      NEW.ward_id       := COALESCE(NEW.ward_id, j.ward_id);
      NEW.local_body_id := COALESCE(NEW.local_body_id, j.local_body_id);
      NEW.taluk_id      := COALESCE(NEW.taluk_id, j.taluk_id);
      NEW.district_id   := COALESCE(NEW.district_id, j.district_id);
    END IF;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_complaint_location BEFORE INSERT OR UPDATE OF latitude, longitude ON complaints.complaint
  FOR EACH ROW EXECUTE FUNCTION complaints.fill_location();

-- =====================================================================
-- VIEWS used by the dashboards
-- =====================================================================
CREATE OR REPLACE VIEW complaints.v_sla_breached AS
SELECT c.*, now() - c.due_date AS overdue_by
FROM complaints.complaint c
WHERE c.status NOT IN ('resolved','closed','rejected') AND c.due_date < now();

CREATE OR REPLACE VIEW complaints.v_department_performance AS
SELECT department_id,
       count(*)                                                   AS total,
       count(*) FILTER (WHERE status IN ('resolved','closed'))    AS resolved,
       count(*) FILTER (WHERE due_date < now() AND status NOT IN ('resolved','closed','rejected')) AS sla_breached,
       avg(resolved_at - created_at) FILTER (WHERE resolved_at IS NOT NULL) AS avg_resolution_time
FROM complaints.complaint
GROUP BY department_id;

-- =====================================================================
-- ROLES & PRIVILEGES (least privilege; passwords come from secrets, not from this file)
-- =====================================================================
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mygovt_app')         THEN CREATE ROLE mygovt_app         NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mygovt_ai_readonly') THEN CREATE ROLE mygovt_ai_readonly NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='mygovt_etl')         THEN CREATE ROLE mygovt_etl         NOLOGIN; END IF;
END $$;

-- AI read-only: knowledge tables only. NO identity, NO complaints, NO audit.
GRANT USAGE ON SCHEMA administration, schemes, services, policies, documents TO mygovt_ai_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA administration, schemes, services, policies, documents TO mygovt_ai_readonly;
GRANT EXECUTE ON FUNCTION administration.resolve_jurisdiction(double precision,double precision) TO mygovt_ai_readonly;

-- App: full DML on operational schemas; INSERT-only on audit.
GRANT USAGE ON SCHEMA system, administration, identity, schemes, services, policies, documents, complaints, ai, audit TO mygovt_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity, complaints, ai TO mygovt_app;
GRANT SELECT ON ALL TABLES IN SCHEMA system, administration, schemes, services, policies, documents TO mygovt_app;
GRANT INSERT, SELECT ON audit.audit_log TO mygovt_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA complaints, audit TO mygovt_app;

-- ETL: write to knowledge schemas + registries only.
GRANT USAGE ON SCHEMA system, administration, schemes, services, policies, documents TO mygovt_etl;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA system, administration, schemes, services, policies, documents TO mygovt_etl;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA administration, schemes, services, policies, documents TO mygovt_etl;

-- Row-level security example: citizens see only their own complaints (enabled in app via SET LOCAL app.citizen_id)
ALTER TABLE complaints.complaint ENABLE ROW LEVEL SECURITY;
CREATE POLICY citizen_own_complaints ON complaints.complaint
  FOR SELECT TO mygovt_app
  USING (
    current_setting('app.role', true) IN ('officer','department_admin','state_admin','system_admin','system')
    OR citizen_id::text = current_setting('app.citizen_id', true)
  );
-- NOTE: permissive policies are OR-ed, so write policies must NOT use USING (true) for SELECT-able commands.
CREATE POLICY app_insert_complaints ON complaints.complaint
  FOR INSERT TO mygovt_app WITH CHECK (true);
CREATE POLICY app_update_complaints ON complaints.complaint
  FOR UPDATE TO mygovt_app
  USING (
    current_setting('app.role', true) IN ('officer','department_admin','state_admin','system_admin','system')
    OR citizen_id::text = current_setting('app.citizen_id', true)
  )
  WITH CHECK (true);
-- No DELETE policy: complaints are never deleted (RLS denies by default).
