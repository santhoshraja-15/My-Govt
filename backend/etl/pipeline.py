"""Staged ingestion of official documents:

    discover -> robots/allow-list -> download -> validate -> extract -> clean -> chunk -> store

Every stage outcome is written to system.ingestion_log; a failure in one document never stops the
run. Nothing is claimed as downloaded unless the bytes were actually fetched and hashed. Documents
land with verification_status='unverified': retrieving a file from an official domain proves its
origin, not that its contents are correct or current.

    python -m etl.pipeline --dsn postgresql://... --source TN_GOV_PORTAL --page https://www.tn.gov.in/ \
        --doc-type Notice --limit 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import asyncpg
import httpx

from etl.cleaners.text import chunk_pages, clean_text, detect_language
from etl.connectors.web import USER_AGENT, Candidate, IngestError, discover_links, download, registered_hosts
from etl.extractors.pdf import extract_pdf

DOC_TYPES = ("GO", "Gazette", "Notice", "Circular", "Policy", "Law", "Rule", "Scheme", "Announcement", "Guideline", "Manual")


async def _log(conn, run_id, url, stage, status, detail=None):
    await conn.execute(
        "INSERT INTO system.ingestion_log (run_id,url,stage,status,detail) VALUES ($1,$2,$3,$4,$5)",
        run_id, url, stage, status, (detail or "")[:500] or None)


async def allowed_hosts(conn) -> set[str]:
    rows = await conn.fetch("SELECT url FROM system.source_registry WHERE source_type='official' AND status='active' AND url IS NOT NULL")
    return registered_hosts([r["url"] for r in rows])


async def ingest_one(conn, client, cand: Candidate, *, run_id, source_id, department_id, doc_type: str,
                     allowed: set[str], data_dir: Path | None, embed_later: bool = True) -> dict:
    """Ingest a single candidate. Returns {'url','outcome','document_id'|'reason'}; never raises IngestError."""
    url = cand.url
    try:
        dl = await download(client, url, allowed)
        await _log(conn, run_id, url, "download", "ok", f"{len(dl.content)} bytes sha256={dl.sha256[:12]}")
    except IngestError as e:
        await _log(conn, run_id, url, e.stage, "failed", e.message)
        return {"url": url, "outcome": "failed", "stage": e.stage, "reason": e.message}

    existing = await conn.fetchval("SELECT document_id FROM documents.document WHERE file_hash=$1", dl.sha256)
    if existing:
        await _log(conn, run_id, url, "store", "skipped", f"duplicate of {existing}")
        return {"url": url, "outcome": "duplicate", "document_id": str(existing)}

    ext = extract_pdf(dl.content)
    await _log(conn, run_id, url, "extract", "ok" if ext.status == "ok" else "failed", ext.error)
    pages = [clean_text(p) for p in ext.pages] if ext.status == "ok" else []
    chunks = chunk_pages(pages) if pages else []
    if ext.status == "ok":
        await _log(conn, run_id, url, "chunk", "ok", f"{len(chunks)} chunks")
    language = detect_language(" ".join(pages)[:20000]) if pages else None

    rel_path = None
    if data_dir is not None:
        target = data_dir / "raw" / "ingested" / f"{dl.sha256}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(dl.content)
        rel_path = f"raw/ingested/{dl.sha256}.pdf"

    async with conn.transaction():
        # a changed file at a known URL supersedes the earlier copy (history is kept, never overwritten)
        await conn.execute("UPDATE documents.document SET status='superseded' WHERE source_url=$1 AND file_hash<>$2 AND status='active'", dl.url, dl.sha256)
        doc_id = await conn.fetchval(
            """INSERT INTO documents.document
               (title, document_type, department_id, source_id, source_url, file_path, file_hash, language,
                full_text, status, retrieved_at, source_document_id, http_status, content_type, page_count,
                extraction_status, extraction_error, verification_status, ingestion_run_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'active',now(),$10,$11,$12,$13,$14,$15,'unverified',$16)
               RETURNING document_id""",
            cand.title[:300], doc_type, department_id, source_id, dl.url, rel_path, dl.sha256, language,
            "\n\n".join(pages) or None, dl.url.rsplit("/", 1)[-1], dl.status, dl.content_type[:100],
            ext.page_count, ext.status, ext.error, run_id)
        if chunks:
            await conn.executemany(
                "INSERT INTO documents.document_chunk (document_id,chunk_number,content,page_number,language) VALUES ($1,$2,$3,$4,$5)",
                [(doc_id, c.number, c.text, c.page, detect_language(c.text)) for c in chunks])
    await _log(conn, run_id, url, "store", "ok", f"document {doc_id}")
    return {"url": url, "outcome": "stored" if ext.status == "ok" else f"stored_{ext.status}", "document_id": str(doc_id),
            "chunks": len(chunks)}


async def run_ingestion(conn, client, candidates: list[Candidate], *, source_code: str, doc_type: str = "Notice",
                        department_code: str | None = None, data_dir: Path | None = None,
                        limit: int | None = None) -> dict:
    if doc_type not in DOC_TYPES:
        raise ValueError(f"doc_type must be one of {DOC_TYPES}")
    if await conn.fetchval("SELECT to_regclass('system.ingestion_log')") is None:
        raise RuntimeError("migration 008 (ingestion tracking) is not applied: run the SQL files in database/migrations/")
    src = await conn.fetchrow("SELECT source_id FROM system.source_registry WHERE source_code=$1 AND source_type='official'", source_code)
    if src is None:
        raise ValueError(f"'{source_code}' is not an approved official source in system.source_registry")
    dept = None
    if department_code:
        dept = await conn.fetchval("SELECT department_id FROM administration.department WHERE department_code=$1", department_code)
        if dept is None:
            raise ValueError(f"unknown department_code '{department_code}'")
    run_id = uuid.uuid4()
    allowed = await allowed_hosts(conn)
    results = []
    for cand in candidates[:limit]:
        results.append(await ingest_one(conn, client, cand, run_id=run_id, source_id=src["source_id"], department_id=dept,
                                        doc_type=doc_type, allowed=allowed, data_dir=data_dir))
    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return {"run_id": str(run_id), "attempted": len(results), "counts": counts,
            "failures": [r for r in results if r["outcome"] == "failed"], "results": results}


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--source", required=True, help="source_code of an approved official source")
    ap.add_argument("--page", help="HTML page on an approved host to scan for PDF links")
    ap.add_argument("--url", action="append", default=[], help="explicit document URL (repeatable)")
    ap.add_argument("--doc-type", default="Notice", choices=DOC_TYPES)
    ap.add_argument("--department", help="department_code")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args(argv)
    conn = await asyncpg.connect(args.dsn)
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
            allowed = await allowed_hosts(conn)
            cands = [Candidate(u, u.rsplit("/", 1)[-1]) for u in args.url]
            if args.page:
                cands += await discover_links(client, args.page, allowed)
            report = await run_ingestion(conn, client, cands, source_code=args.source, doc_type=args.doc_type,
                                         department_code=args.department, data_dir=Path(args.data_dir), limit=args.limit)
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2, default=str))
        return 1 if report["failures"] and not report["counts"].get("stored") else 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
