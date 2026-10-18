"""Retrieval evaluation against a golden set.   python -m ai.eval.run_all [--dsn ...] [--provider local|test|none]

Measures what actually decides answer quality here - whether the right records are cited and whether
unanswerable questions are refused - using the SAME retrieval code as the assistant. Use it to
re-calibrate RETRIEVAL_MIN_SIMILARITY whenever the embedding model, corpus or weights change.

Cases live in ai/eval/golden_cases.json:
  {"question": "...", "expect": "answer", "titles_any": ["Breakfast"]}   cited titles must include one of these
  {"question": "...", "expect": "abstain"}                              nothing may be cited
Exit code 1 when a metric falls below its threshold.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.embeddings.providers import EmbeddingError, get_provider
from app.core.config import settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

CASES = Path(__file__).with_name("golden_cases.json")


def default_url() -> str:
    g = os.getenv
    return "postgresql+asyncpg://{u}:{p}@{h}:{port}/{db}".format(
        u=quote(g("POSTGRES_USER", settings.POSTGRES_USER)), p=quote(g("POSTGRES_PASSWORD", settings.POSTGRES_PASSWORD)),
        h=g("POSTGRES_HOST", settings.POSTGRES_HOST), port=g("POSTGRES_PORT", str(settings.POSTGRES_PORT)),
        db=g("POSTGRES_DB", settings.POSTGRES_DB))


def score(cases: list[dict], results: list[dict]) -> dict:
    """Pure metric computation. results[i] = {'abstained': bool, 'titles': [cited titles]}."""
    ans = [(c, r) for c, r in zip(cases, results, strict=True) if c["expect"] == "answer"]
    abst = [(c, r) for c, r in zip(cases, results, strict=True) if c["expect"] == "abstain"]
    hit = [any(any(t.lower() in title.lower() for title in r["titles"]) for t in c["titles_any"]) for c, r in ans]
    top1 = [bool(r["titles"]) and any(t.lower() in r["titles"][0].lower() for t in c["titles_any"]) for c, r in ans]
    refused = [r["abstained"] and not r["titles"] for _, r in abst]
    return {
        "answerable": len(ans), "hit_rate": sum(hit) / len(ans) if ans else None,
        "top1_rate": sum(top1) / len(ans) if ans else None,
        "unanswerable": len(abst), "abstain_accuracy": sum(refused) / len(abst) if abst else None,
        "failures": [c["question"] for (c, _), ok in zip(ans, hit, strict=True) if not ok]
        + [c["question"] for (c, _), ok in zip(abst, refused, strict=True) if not ok],
    }


async def evaluate(session_factory, cases: list[dict], embedder) -> dict:
    results = []
    for c in cases:
        async with session_factory() as db:
            svc = ChatService(db, llm=None, embedder=embedder)
            r = await svc.process_message(ChatRequest(message=c["question"]), None)
        results.append({"abstained": r.abstained, "titles": [x.title for x in r.citations]})
    return score(cases, results)


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", help="postgresql+asyncpg://... (default: POSTGRES_* env)")
    ap.add_argument("--provider", default=None, help="embedding provider: local | openai | test | none (keyword only)")
    ap.add_argument("--cases", default=str(CASES))
    ap.add_argument("--min-hit-rate", type=float, default=0.8)
    ap.add_argument("--min-abstain", type=float, default=1.0)
    args = ap.parse_args(argv)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    embedder = None if args.provider == "none" else get_provider(args.provider)
    engine = create_async_engine((args.dsn or default_url()).replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        sf = async_sessionmaker(engine, expire_on_commit=False)
        if args.provider == "none":                       # force keyword-only: query embedding "fails"
            class _NoVectors:
                name, model, dimension = "none", "none", settings.EMBEDDING_DIMENSION

                async def embed(self, texts):
                    raise EmbeddingError("semantic search disabled for this evaluation")  # -> keyword-only path

            embedder = _NoVectors()
        m = await evaluate(sf, cases, embedder)
    finally:
        await engine.dispose()
    print(json.dumps({"min_similarity": settings.RETRIEVAL_MIN_SIMILARITY, **m}, indent=2))
    ok = (m["hit_rate"] is None or m["hit_rate"] >= args.min_hit_rate) and \
         (m["abstain_accuracy"] is None or m["abstain_accuracy"] >= args.min_abstain)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
