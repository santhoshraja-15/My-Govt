-- =====================================================================
-- Migration 008: document-ingestion provenance and tracking
--   documents.document      retrieval timestamp, source document id, HTTP/content facts, extraction
--                           status/error, verification status (default 'unverified': a copy fetched
--                           from an official domain is NOT thereby verified content)
--   documents.document_chunk  embedding model, hash of the embedded text, failure reason
--   system.ingestion_log      one row per pipeline stage per URL (success, skip, failure)
-- Idempotent.
-- =====================================================================
ALTER TABLE documents.document
  ADD COLUMN IF NOT EXISTS retrieved_at       timestamptz,
  ADD COLUMN IF NOT EXISTS source_document_id text,
  ADD COLUMN IF NOT EXISTS http_status        int,
  ADD COLUMN IF NOT EXISTS content_type       text,
  ADD COLUMN IF NOT EXISTS page_count         int,
  ADD COLUMN IF NOT EXISTS extraction_status  text NOT NULL DEFAULT 'pending'
    CHECK (extraction_status IN ('pending','ok','empty','failed')),
  ADD COLUMN IF NOT EXISTS extraction_error   text,
  ADD COLUMN IF NOT EXISTS verification_status text NOT NULL DEFAULT 'unverified'
    CHECK (verification_status IN ('official_verified','externally_referenced','provisional','unverified','deprecated')),
  ADD COLUMN IF NOT EXISTS ingestion_run_id   uuid;

ALTER TABLE documents.document_chunk
  ADD COLUMN IF NOT EXISTS embedding_model     text,
  ADD COLUMN IF NOT EXISTS embedded_text_hash  text,
  ADD COLUMN IF NOT EXISTS embedding_error     text,
  ADD COLUMN IF NOT EXISTS embedded_at         timestamptz;

CREATE INDEX IF NOT EXISTS idx_chunk_needs_embedding
  ON documents.document_chunk (document_id) WHERE embedding IS NULL;

CREATE TABLE IF NOT EXISTS system.ingestion_log (
  log_id     bigserial PRIMARY KEY,
  run_id     uuid NOT NULL,
  url        text,
  stage      text NOT NULL CHECK (stage IN ('discover','robots','download','validate','extract','clean','chunk','store','embed')),
  status     text NOT NULL CHECK (status IN ('ok','skipped','failed')),
  detail     text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ingestion_log_run ON system.ingestion_log (run_id, log_id);
