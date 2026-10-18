"""Generate and store embeddings.   python -m app.ai.embeddings.run --all

Targets: document chunks (tracked: model + hash of the embedded text), schemes and services.
A chunk is (re-)embedded when it has no embedding, its text changed since it was embedded, or it
was embedded with a different model. Re-running when nothing changed does nothing.
Failures never abort the run: a failed batch records `embedding_error` on its chunks and the run
continues; the exit code is non-zero if anything failed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from typing import Any
from urllib.parse import quote

import asyncpg
import structlog

from app.ai.embeddings.providers import (
    DimensionMismatch, EmbeddingError, EmbeddingProvider, check_dimensions, get_provider,
)
from app.core.config import settings

logger = structlog.get_logger(__name__)
MAX_ATTEMPTS = 4


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.8g}" for x in vec) + "]"


async def embed_with_retry(provider: EmbeddingProvider, texts: list[str], sleep=asyncio.sleep) -> list[list[float]]:
    """Retry transient failures (network, 5xx, 429 honouring Retry-After); fail fast on everything else."""
    delay = 0.5
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            vectors = await provider.embed(texts)
            # validate against the DATABASE column size here, whatever the provider claims
            check_dimensions(vectors, settings.EMBEDDING_DIMENSION, len(texts))
            return vectors
        except DimensionMismatch:
            raise
        except EmbeddingError as e:
            if not e.retryable or attempt == MAX_ATTEMPTS:
                raise
            await sleep(min(e.retry_after if e.retry_after is not None else delay, 30))
            delay *= 2
    raise AssertionError("unreachable")


async def embed_chunks(conn, provider: EmbeddingProvider, *, batch_size: int = 32, limit: int | None = None,
                       reembed: bool = False, sleep=asyncio.sleep) -> dict:
    rows = await conn.fetch(
        """SELECT chunk_id, content, embedding IS NOT NULL AS has_vec, embedded_text_hash, embedding_model
           FROM documents.document_chunk
           WHERE $1 OR embedding IS NULL OR embedding_model IS DISTINCT FROM $2
           ORDER BY document_id, chunk_number""", reembed, provider.model)
    todo = [r for r in rows if reembed or not r["has_vec"] or r["embedding_model"] != provider.model
            or r["embedded_text_hash"] != text_hash(r["content"])]
    # also catch edited text on chunks that already carry this model's vector
    changed = await conn.fetch(
        "SELECT chunk_id, content, embedded_text_hash FROM documents.document_chunk "
        "WHERE embedding IS NOT NULL AND embedding_model = $1", provider.model)
    seen = {r["chunk_id"] for r in todo}
    for r in changed:
        if r["chunk_id"] not in seen and r["embedded_text_hash"] != text_hash(r["content"]):
            todo.append(r)
    if limit is not None:
        todo = todo[:limit]
    stats = {"selected": len(todo), "embedded": 0, "failed": 0, "skipped_up_to_date": 0}
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        texts = [r["content"] for r in batch]
        try:
            vectors = await embed_with_retry(provider, texts, sleep)
        except EmbeddingError as e:
            stats["failed"] += len(batch)
            await conn.execute("UPDATE documents.document_chunk SET embedding_error=$2 WHERE chunk_id = ANY($1)",
                               [r["chunk_id"] for r in batch], str(e)[:300])
            logger.warning("embedding_batch_failed", size=len(batch), error=str(e))
            continue
        async with conn.transaction():
            await conn.executemany(
                "UPDATE documents.document_chunk SET embedding=$2::vector, embedding_model=$3, embedded_text_hash=$4, "
                "embedding_error=NULL, embedded_at=now() WHERE chunk_id=$1",
                [(r["chunk_id"], to_vector_literal(v), provider.model, text_hash(r["content"])) for r, v in zip(batch, vectors, strict=True)])
        stats["embedded"] += len(batch)
    return stats


def _scheme_text(r) -> str:
    return " . ".join(x for x in (r["scheme_name"], r["short_description"], r["benefits_summary"], r["full_description"]) if x)


async def embed_catalogue(conn, provider: EmbeddingProvider, table: str, *, batch_size: int = 32, reembed: bool = False,
                          sleep=asyncio.sleep) -> dict:
    """schemes.scheme / services.service: embed rows lacking a vector (all rows with reembed)."""
    if table == "schemes.scheme":
        rows = await conn.fetch("SELECT scheme_id AS id, scheme_name, short_description, benefits_summary, full_description "
                                "FROM schemes.scheme WHERE $1 OR embedding IS NULL ORDER BY scheme_code", reembed)
        texts = [_scheme_text(r) for r in rows]
        sql = "UPDATE schemes.scheme SET embedding=$2::vector WHERE scheme_id=$1"
    elif table == "services.service":
        rows = await conn.fetch("SELECT service_id AS id, service_name, description FROM services.service "
                                "WHERE $1 OR embedding IS NULL ORDER BY service_code", reembed)
        texts = [" . ".join(x for x in (r["service_name"], r["description"]) if x) for r in rows]
        sql = "UPDATE services.service SET embedding=$2::vector WHERE service_id=$1"
    else:
        raise ValueError(table)
    stats = {"selected": len(rows), "embedded": 0, "failed": 0}
    for i in range(0, len(rows), batch_size):
        try:
            vecs = await embed_with_retry(provider, texts[i:i + batch_size], sleep)
        except EmbeddingError as e:
            stats["failed"] += len(rows[i:i + batch_size])
            logger.warning("embedding_batch_failed", table=table, error=str(e))
            continue
        async with conn.transaction():
            await conn.executemany(sql, [(r["id"], to_vector_literal(v)) for r, v in zip(rows[i:i + batch_size], vecs, strict=True)])
        stats["embedded"] += len(vecs)
    return stats


def default_dsn() -> str:
    g = os.getenv
    return "postgresql://{u}:{p}@{h}:{port}/{db}".format(
        u=quote(g("POSTGRES_USER", settings.POSTGRES_USER)), p=quote(g("POSTGRES_PASSWORD", settings.POSTGRES_PASSWORD)),
        h=g("POSTGRES_HOST", settings.POSTGRES_HOST), port=g("POSTGRES_PORT", str(settings.POSTGRES_PORT)),
        db=g("POSTGRES_DB", settings.POSTGRES_DB))


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="document chunks + schemes + services")
    ap.add_argument("--documents", action="store_true")
    ap.add_argument("--schemes", action="store_true")
    ap.add_argument("--services", action="store_true")
    ap.add_argument("--provider", help="override EMBEDDING_PROVIDER (local|openai|test)")
    ap.add_argument("--batch-size", type=int, default=settings.EMBEDDING_BATCH_SIZE)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--reembed", action="store_true", help="recompute even if up to date")
    ap.add_argument("--dsn")
    args = ap.parse_args(argv)
    if not (args.all or args.documents or args.schemes or args.services):
        ap.error("choose --all, --documents, --schemes or --services")
    provider = get_provider(args.provider)
    if provider.dimension != settings.EMBEDDING_DIMENSION:
        raise SystemExit(f"provider dimension {provider.dimension} != EMBEDDING_DIMENSION {settings.EMBEDDING_DIMENSION}")
    conn = await asyncpg.connect((args.dsn or default_dsn()).replace("postgresql+asyncpg://", "postgresql://"))
    try:
        dim = await conn.fetchval("SELECT atttypmod FROM pg_attribute WHERE attrelid='documents.document_chunk'::regclass AND attname='embedding'")
        if dim != provider.dimension:
            raise SystemExit(f"database column is vector({dim}) but the provider produces {provider.dimension}-d vectors")
        report: dict[str, Any] = {"provider": provider.name, "model": provider.model}
        if args.all or args.documents:
            report["chunks"] = await embed_chunks(conn, provider, batch_size=args.batch_size, limit=args.limit, reembed=args.reembed)
        if args.all or args.schemes:
            report["schemes"] = await embed_catalogue(conn, provider, "schemes.scheme", batch_size=args.batch_size, reembed=args.reembed)
        if args.all or args.services:
            report["services"] = await embed_catalogue(conn, provider, "services.service", batch_size=args.batch_size, reembed=args.reembed)
        print(report)
        failed = sum(v.get("failed", 0) for v in report.values() if isinstance(v, dict))
        return 1 if failed else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
