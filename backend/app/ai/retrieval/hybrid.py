"""Hybrid retrieval over documents, schemes and services: keyword (full-text) + vector similarity, fused
with source reliability and freshness on ONE scale so different record types compete fairly.

Only the signals that are actually available are used and the weights (settings.HYBRID_WEIGHT_*) are
renormalised over them, so a database without embeddings still retrieves (keyword only) and says so.
A vector hit with no keyword match must reach settings.RETRIEVAL_MIN_SIMILARITY, and keyword hits far
weaker than the best keyword hit of their type are dropped, so generic words cannot flood the evidence.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.providers import EmbeddingError, EmbeddingProvider, get_provider
from app.core.config import settings

logger = structlog.get_logger(__name__)
_provider_cache: dict[str, EmbeddingProvider] = {}

REL_KEYWORD_CUTOFF = 0.3                       # keyword hit must reach 30% of the best hit of its type
QUOTAS = {"document_chunk": 4, "scheme": 3, "service": 3}


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


async def query_vector(db: AsyncSession, question: str, embedder: Optional[EmbeddingProvider], info: dict) -> Optional[str]:
    """pgvector literal for the question, or None (with an explanatory note) when semantic search is not possible."""
    embedder = embedder if embedder is not None else get_cached_provider()
    if embedder is None:
        return None
    has_vec = (await db.execute(text(
        "SELECT EXISTS (SELECT 1 FROM documents.document_chunk WHERE embedding IS NOT NULL AND embedding_model = :m) "
        "OR EXISTS (SELECT 1 FROM schemes.scheme WHERE embedding IS NOT NULL)"), {"m": embedder.model})).scalar()
    if not has_vec:
        info["notes"].append("Embeddings have not been generated yet; results use keyword matching only.")
        return None
    try:
        qv = (await embedder.embed([question]))[0]
    except EmbeddingError as e:
        info["notes"].append("Semantic search was unavailable; results use keyword matching only.")
        logger.warning("query_embedding_failed", error=str(e))
        return None
    info["semantic"] = True
    info["model"] = embedder.model
    return "[" + ",".join(f"{x:.8g}" for x in qv) + "]"


_CHUNK_BASE = """
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

_CATALOGUE = {
    "scheme": """
        SELECT {extra} s.scheme_id::text AS entity_id, s.scheme_name AS title, s.short_description AS description,
               d.department_name, 'scheme' AS entity_type, s.verified_at::text AS verified_at,
               coalesce(s.official_url, sr.url) AS source_url, coalesce(sr.reliability_score, 0.5)::float AS reliability,
               s.verification_status, s.source_document_ref,
               (SELECT string_agg(er.human_readable, '; ' ORDER BY er.rule_group, er.attribute)
                  FROM schemes.eligibility_rule er WHERE er.scheme_id = s.scheme_id AND er.human_readable IS NOT NULL) AS rules_text
        FROM schemes.scheme s
        LEFT JOIN administration.department d ON d.department_id = s.department_id
        LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
        WHERE s.status = 'active' AND s.verification_status <> 'deprecated'
    """,
    "service": """
        SELECT {extra} s.service_id::text AS entity_id, s.service_name AS title, s.description,
               d.department_name, 'service' AS entity_type, s.verified_at::text AS verified_at,
               coalesce(s.official_url, s.application_url, sr.url) AS source_url, coalesce(sr.reliability_score, 0.5)::float AS reliability,
               s.verification_status, s.source_document_ref
        FROM services.service s
        LEFT JOIN administration.department d ON d.department_id = s.department_id
        LEFT JOIN system.source_registry sr ON sr.source_id = s.source_id
        WHERE s.status = 'active' AND s.verification_status <> 'deprecated'
    """,
}
_KW = {
    "document_chunk": ("ts_rank(c.tsv, to_tsquery('simple', :tsq))::float", "c.tsv @@ to_tsquery('simple', :tsq)", "c"),
    "scheme": ("ts_rank(s.tsv, to_tsquery('simple', :tsq))::float", "s.tsv @@ to_tsquery('simple', :tsq)", "s"),
    "service": (
        "ts_rank(to_tsvector('simple', coalesce(s.service_name,'') || ' ' || coalesce(s.description,'')), to_tsquery('simple', :tsq))::float",
        "to_tsvector('simple', coalesce(s.service_name,'') || ' ' || coalesce(s.description,'')) @@ to_tsquery('simple', :tsq)", "s"),
}


async def _candidates(db: AsyncSession, kind: str, tsq: Optional[str], qv: Optional[str], model: Optional[str], n: int) -> dict[str, dict]:
    """Keyword and vector candidates of one kind, merged by id, with kw normalised within the kind."""
    key = "chunk_id" if kind == "document_chunk" else "entity_id"
    base = _CHUNK_BASE if kind == "document_chunk" else _CATALOGUE[kind]
    kw_expr, kw_filter, alias = _KW[kind]
    found: dict[str, dict] = {}
    if tsq:
        # when a query vector exists also read each keyword hit's own similarity (NULL if it has no usable vector)
        has_vec = f"{alias}.embedding IS NOT NULL" + (" AND c.embedding_model = :m" if kind == "document_chunk" else "")
        sem_col = f"CASE WHEN {has_vec} THEN (1 - ({alias}.embedding <=> CAST(:qv AS vector)))::float END AS sem_kw," if qv else ""
        params_kw: dict[str, Any] = {"tsq": tsq, "n": n, **({"qv": qv} if qv else {}), **({"m": model} if qv and kind == "document_chunk" else {})}
        rows = (await db.execute(text(base.format(extra=f"{sem_col} {kw_expr} AS kw_raw,") + f" AND {kw_filter} ORDER BY kw_raw DESC LIMIT :n"),
                                 params_kw)).fetchall()
        top = max((r.kw_raw for r in rows), default=0.0) or 1.0
        for r in rows:
            rec = {k: v for k, v in r._mapping.items() if k != "sem_kw"}
            sem_kw = r._mapping.get("sem_kw")
            found[getattr(r, key)] = {**rec, "kw": r.kw_raw / top, "sem": max(min(float(sem_kw), 1.0), 0.0) if sem_kw is not None else None}
    if qv:
        cond = f" AND {alias}.embedding IS NOT NULL"
        params: dict[str, Any] = {"qv": qv, "n": n}
        if kind == "document_chunk":
            cond += " AND c.embedding_model = :m"
            params["m"] = model
        extra = f"(1 - ({alias}.embedding <=> CAST(:qv AS vector)))::float AS sim,"
        rows = (await db.execute(text(base.format(extra=extra) + cond + f" ORDER BY {alias}.embedding <=> CAST(:qv AS vector) LIMIT :n"), params)).fetchall()
        for r in rows:
            rec = found.setdefault(getattr(r, key), {**{k: v for k, v in r._mapping.items() if k != "sim"}, "kw": None, "sem": None})
            rec["sem"] = max(min(float(r.sim), 1.0), 0.0)
    return found


async def search(db: AsyncSession, query_tsquery: Optional[str], question: str, *, kinds: tuple[str, ...] = ("document_chunk", "scheme", "service"),
                 limit: int = 8, embedder: Optional[EmbeddingProvider] = None, today: Optional[date] = None) -> tuple[list[dict], dict]:
    """Return (ranked candidates, info). Every candidate has `score` and `kind`; chunks also carry page/outdated."""
    today = today or datetime.now(timezone.utc).date()
    info: dict = {"semantic": False, "keyword": query_tsquery is not None, "notes": []}
    qv = await query_vector(db, question, embedder, info)
    model = info.get("model")
    pool: list[dict] = []
    for kind in kinds:
        cands = await _candidates(db, kind, query_tsquery, qv, model, limit * 3)
        for v in cands.values():
            kw, sem = v.get("kw"), v.get("sem")
            if info["semantic"] and sem is not None:
                keep = sem >= settings.RETRIEVAL_MIN_SIMILARITY       # the vector engine judged it: a stray keyword cannot rescue it
            else:                                                     # never embedded / no vectors: keyword evidence only
                keep = kw is not None and kw >= REL_KEYWORD_CUTOFF
            if not keep:
                continue            # not evidence
            v["score"] = combine_scores(
                keyword=(kw or 0.0) if info["keyword"] else None, semantic=(sem or 0.0) if info["semantic"] else None,
                reliability=v["reliability"], freshness=freshness_score(v.get("publication_date"), v.get("retrieved_at"), today))
            v["kind"] = kind
            v["outdated"] = bool(v.get("expiry_date") and v["expiry_date"] < today)
            pool.append(v)
    pool.sort(key=lambda x: (-x["score"], str(x.get("chunk_id") or x.get("entity_id"))))
    out: list[dict] = []
    used = {k: 0 for k in QUOTAS}
    for v in pool:
        if used[v["kind"]] >= QUOTAS[v["kind"]]:
            continue                # per-type quota: no record type may crowd out the others
        used[v["kind"]] += 1
        out.append(v)
        if len(out) == limit:
            break
    return out, info


async def search_chunks(db: AsyncSession, query_tsquery: Optional[str], question: str, *, limit: int = 6,
                        embedder: Optional[EmbeddingProvider] = None, today: Optional[date] = None) -> tuple[list[dict], dict]:
    """Document passages only."""
    return await search(db, query_tsquery, question, kinds=("document_chunk",), limit=limit, embedder=embedder, today=today)


__all__ = ["search", "search_chunks", "combine_scores", "freshness_score", "get_cached_provider"]
