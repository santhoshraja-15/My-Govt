"""Hybrid retrieval over ingested document chunks: keyword (full-text) + vector similarity, fused with
source reliability and freshness. Only the signals that are actually available are used and the
weights (settings.HYBRID_WEIGHT_*) are renormalised over them, so a database without embeddings still
retrieves (keyword only) and says so."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.providers import EmbeddingError, EmbeddingProvider, get_provider
from app.core.config import settings

logger = structlog.get_logger(__name__)
_provider_cache: dict[str, EmbeddingProvider] = {}


def freshness_score(published: Optional[date], retrieved: Optional[datetime], today: date) -> float:
    """1.0 for brand-new, decaying with age (half-life ~1 year). Unknown dates score 0.5 (neutral)."""
    ref = published or (retrieved.date() if retrieved else None)
    if ref is None:
        return 0.5
    age_days = max((today - ref).days, 0)
    return 1.0 / (1.0 + age_days / 365.0)


def combine_scores(*, keyword: Optional[float], semantic: Optional[float], reliability: float, freshness: float) -> float:
    """Weighted mean over the available signals (weights renormalised)."""
    parts = [(settings.HYBRID_WEIGHT_RELIABILITY, reliability), (settings.HYBRID_WEIGHT_FRESHNESS, freshness)]
    if keyword is not None:
        parts.append((settings.HYBRID_WEIGHT_KEYWORD, keyword))
    if semantic is not None:
        parts.append((settings.HYBRID_WEIGHT_SEMANTIC, semantic))
    total = sum(w for w, _ in parts)
    return round(sum(w * v for w, v in parts) / total, 4)


def get_cached_provider(name: Optional[str] = None) -> Optional[EmbeddingProvider]:
    """Embedding provider for query vectors, or None if unavailable (keyword-only retrieval)."""
    key = (name or settings.EMBEDDING_PROVIDER).lower()
    if key not in _provider_cache:
        try:
            _provider_cache[key] = get_provider(key)
        except EmbeddingError as e:
            logger.warning("embedding_provider_unavailable", provider=key, error=str(e))
            return None
    return _provider_cache[key]


async def search_chunks(db: AsyncSession, query_tsquery: Optional[str], question: str, *, limit: int = 6,
                        embedder: Optional[EmbeddingProvider] = None, today: Optional[date] = None) -> tuple[list[dict], dict]:
    """Return (passages, info). info = {"semantic": bool, "keyword": bool, "notes": [...]}."""
    today = today or datetime.now(timezone.utc).date()
    info: dict = {"semantic": False, "keyword": query_tsquery is not None, "notes": []}
    base = """
        SELECT {extra} c.chunk_id::text AS chunk_id, c.document_id::text AS document_id, c.content, c.page_number,
               d.title, d.document_type, d.source_url, d.retrieved_at, d.publication_date, d.expiry_date,
               d.verification_status, dep.department_name,
               coalesce(sr.reliability_score, 0.5)::float AS reliability
        FROM documents.document_chunk c
        JOIN documents.document d ON d.document_id = c.document_id
        LEFT JOIN administration.department dep ON dep.department_id = d.department_id
        LEFT JOIN system.source_registry sr ON sr.source_id = d.source_id
        WHERE d.status = 'active' AND d.extraction_status = 'ok' AND d.verification_status <> 'deprecated'
    """
    found: dict[str, dict] = {}
    if query_tsquery:
        rows = (await db.execute(text(base.format(extra="ts_rank(c.tsv, to_tsquery('simple', :tsq))::float AS kw_raw,") + """
            AND c.tsv @@ to_tsquery('simple', :tsq)
            ORDER BY kw_raw DESC, c.chunk_id LIMIT :n"""), {"tsq": query_tsquery, "n": limit * 3})).fetchall()
        top = max((float(r.kw_raw) for r in rows), default=0.0) or 1.0
        for r in rows:
            found[r.chunk_id] = {**dict(r._mapping), "kw": float(r.kw_raw) / top, "sem": None}
    embedder = embedder if embedder is not None else get_cached_provider()
    if embedder is not None:
        has_vec = (await db.execute(text("SELECT EXISTS (SELECT 1 FROM documents.document_chunk WHERE embedding IS NOT NULL AND embedding_model = :m)"),
                                    {"m": embedder.model})).scalar()
        if has_vec:
            try:
                qv = (await embedder.embed([question]))[0]
                lit = "[" + ",".join(f"{x:.8g}" for x in qv) + "]"
                vrows = (await db.execute(text(base.format(extra="(1 - (c.embedding <=> CAST(:qv AS vector)))::float AS sim,") + """
                    AND c.embedding IS NOT NULL AND c.embedding_model = :m
                    ORDER BY c.embedding <=> CAST(:qv AS vector), c.chunk_id LIMIT :n"""), {"m": embedder.model, "qv": lit, "n": limit * 3})).fetchall()
                for r in vrows:
                    rec = found.setdefault(r.chunk_id, {**{k: v for k, v in r._mapping.items() if k != "sim"}, "kw": None, "sem": None})
                    rec["sem"] = max(min(float(r.sim), 1.0), 0.0)
                info["semantic"] = True
            except EmbeddingError as e:
                info["notes"].append("Semantic search was unavailable; results use keyword matching only.")
                logger.warning("query_embedding_failed", error=str(e))
        else:
            info["notes"].append("Document embeddings have not been generated yet; results use keyword matching only.")
    out = []
    for v in found.values():
        sem, kw = v.get("sem"), v.get("kw")
        if not kw and (sem or 0.0) < settings.RETRIEVAL_MIN_SIMILARITY:
            continue                       # irrelevant nearest neighbour: not evidence
        # a hit found by only one method scores 0 on the other so mixed results are comparable
        if info["semantic"]:
            sem = sem or 0.0
        if info["keyword"]:
            kw = kw or 0.0
        v["score"] = combine_scores(keyword=kw if info["keyword"] else None, semantic=sem if info["semantic"] else None,
                                    reliability=v["reliability"], freshness=freshness_score(v["publication_date"], v["retrieved_at"], today))
        v["outdated"] = bool(v["expiry_date"] and v["expiry_date"] < today)
        out.append(v)
    out.sort(key=lambda x: (-x["score"], x["chunk_id"]))
    return out[:limit], info


__all__ = ["search_chunks", "combine_scores", "freshness_score", "get_cached_provider"]
