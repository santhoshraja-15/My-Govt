"""Document ingestion pipeline: discovery, validation, extraction, chunking, storage, failure reporting."""
import hashlib
import uuid

import httpx
import pymupdf
import pytest

from etl.cleaners.text import chunk_pages, clean_text, detect_language
from etl.connectors.web import Candidate, IngestError, discover_links, download, host_allowed, registered_hosts
from etl.pipeline import run_ingestion

BASE = "https://cms.tn.gov.in/docs"


def make_pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        y = 72
        for line in text.split("\n"):
            page.insert_text((72, y), line, fontsize=11)
            y += 16
    data = doc.tobytes()
    doc.close()
    return data


GO_PDF = make_pdf(
    "Government Order Ms No 12\nSchool Education Department\nPage one describes the breakfast programme for primary students.",
    "Page two lists the eligible schools and the monthly review procedure for district officers.",
)


class FakeSite:
    """httpx MockTransport handler with per-path behaviour and a request log."""

    def __init__(self):
        self.routes: dict[str, object] = {}
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return self.routes.get("robots", httpx.Response(404))
        route = self.routes.get(str(request.url)) or self.routes.get(request.url.path)
        if route is None:
            return httpx.Response(404, text="not found")
        if callable(route):
            return route(request)
        return route


@pytest.fixture
def site():
    return FakeSite()


@pytest.fixture
def client(site):
    return httpx.AsyncClient(transport=httpx.MockTransport(site))


ALLOWED = {"tn.gov.in"}


def pdf_response(data=GO_PDF):
    return httpx.Response(200, content=data, headers={"content-type": "application/pdf"})


# -- pure helpers --------------------------------------------------------------------------------
def test_host_allow_list_matches_registered_domain_and_subdomains_only():
    allowed = registered_hosts(["https://www.tn.gov.in", "https://www.esevai.tn.gov.in", None])
    assert allowed == {"tn.gov.in", "esevai.tn.gov.in"}
    assert host_allowed("https://cms.tn.gov.in/a.pdf", allowed)
    assert not host_allowed("https://tn.gov.in.evil.com/a.pdf", allowed)
    assert not host_allowed("https://nottn.gov.in/a.pdf", allowed)
    assert not host_allowed("not a url", allowed)


def test_clean_text_repairs_wraps_and_drops_control_characters():
    raw = "Eligibility is deter-\nmined by the Collec­tor.\nSecond\x00 line.\n\n\n\nNew paragraph"
    out = clean_text(raw)
    assert "determined" in out and "Collector" in out and "\x00" not in out
    assert out.count("\n\n") == 1 and "Second line." in out


def test_language_detection():
    assert detect_language("The scheme provides support") == "en"
    assert detect_language("முதலமைச்சரின் காலை உணவுத் திட்டம் பள்ளி மாணவர்கள்") == "ta"
    assert detect_language("Scheme திட்டம் name") == "mixed"
    assert detect_language("1234 !!!") == "en"


def test_chunks_respect_page_boundaries_size_and_numbering():
    long = " ".join(f"Sentence number {i} about the programme." for i in range(120))
    chunks = chunk_pages(["Short first page.", long, "Last page text."], max_chars=500, overlap=50)
    assert [c.number for c in chunks] == list(range(len(chunks)))
    assert all(len(c.text) <= 520 for c in chunks)
    assert {c.page for c in chunks} == {1, 2, 3}
    assert [c.page for c in chunks] == sorted(c.page for c in chunks)
    assert chunks[0].text == "Short first page." and chunks[-1].text == "Last page text."
    with pytest.raises(ValueError):
        chunk_pages(["x"], max_chars=100, overlap=100)


def test_chunking_is_deterministic():
    pages = ["Para one.\n\nPara two is here.\n\nPara three."]
    assert chunk_pages(pages) == chunk_pages(pages)


# -- connector -----------------------------------------------------------------------------------
async def test_discovery_finds_pdf_links_on_approved_hosts_only(site, client):
    site.routes["/list"] = httpx.Response(200, text=(
        '<a href="/files/a.pdf">Order A</a> <a href="https://cms.tn.gov.in/b.pdf"><b>Order</b> B</a>'
        '<a href="https://evil.example.com/c.pdf">Evil</a> <a href="/files/a.pdf">dup</a> <a href="/page.html">html</a>'))
    found = await discover_links(client, "https://www.tn.gov.in/list", ALLOWED)
    assert [(c.url, c.title) for c in found] == [("https://www.tn.gov.in/files/a.pdf", "Order A"),
                                                  ("https://cms.tn.gov.in/b.pdf", "Order B")]


async def test_discovery_reports_unreachable_listing(site, client):
    with pytest.raises(IngestError) as e:
        await discover_links(client, "https://www.tn.gov.in/missing", ALLOWED)
    assert e.value.stage == "discover" and "404" in e.value.message


async def test_download_rejections(site, client):
    site.routes["/docs/html.pdf"] = httpx.Response(200, text="<html>login</html>", headers={"content-type": "text/html"})
    site.routes["/docs/big.pdf"] = pdf_response(b"%PDF-" + b"0" * 5000)
    site.routes["/docs/missing.pdf"] = httpx.Response(404)
    site.routes["/docs/redir.pdf"] = httpx.Response(302, headers={"location": "https://evil.example.com/x.pdf"})
    site.routes["robots"] = httpx.Response(200, text="User-agent: *\nDisallow: /private/")
    site.routes["/private/secret.pdf"] = pdf_response()
    cases = [
        ("https://evil.example.com/a.pdf", "validate", "allow-list"),
        (f"{BASE}/html.pdf", "validate", "not a PDF"),
        (f"{BASE}/missing.pdf", "download", "404"),
        ("https://cms.tn.gov.in/private/secret.pdf", "robots", "robots"),
    ]
    for url, stage, needle in cases:
        with pytest.raises(IngestError) as e:
            await download(client, url, ALLOWED)
        assert (e.value.stage, needle in e.value.message) == (stage, True), (url, e.value.message)
    with pytest.raises(IngestError) as e:
        await download(client, f"{BASE}/big.pdf", ALLOWED, max_bytes=1000)
    assert "too large" in e.value.message


async def test_transient_errors_are_retried_then_succeed(site, client):
    attempts = {"n": 0}

    def flaky(request):
        attempts["n"] += 1
        return httpx.Response(503) if attempts["n"] < 3 else pdf_response()

    site.routes["/docs/flaky.pdf"] = flaky
    dl = await download(client, f"{BASE}/flaky.pdf", ALLOWED)
    assert attempts["n"] == 3 and dl.sha256 == hashlib.sha256(GO_PDF).hexdigest()


async def test_persistent_server_error_gives_up_with_a_reason(site, client):
    site.routes["/docs/down.pdf"] = httpx.Response(503)
    with pytest.raises(IngestError) as e:
        await download(client, f"{BASE}/down.pdf", ALLOWED)
    assert e.value.stage == "download" and "503" in e.value.message
    assert sum(1 for c in site.calls if c.endswith("/down.pdf")) == 3      # bounded retries


async def test_redirect_to_unapproved_host_is_refused(site, client):
    site.routes["/docs/redir.pdf"] = httpx.Response(302, headers={"location": "https://evil.example.com/x.pdf"})
    site.routes["/docs/x.pdf"] = pdf_response()
    with pytest.raises(IngestError) as e:
        await download(client, f"{BASE}/redir.pdf", ALLOWED)
    assert "allow-list" in e.value.message or "redirected" in e.value.message


# -- pipeline against the database ---------------------------------------------------------------
pytestmark_db = pytest.mark.db


@pytest.fixture
async def clean_docs(conn):
    yield
    await conn.execute("DELETE FROM documents.document WHERE source_url LIKE 'https://%tn.gov.in/docs/%'")
    await conn.execute("DELETE FROM system.ingestion_log")


async def ingest(conn, client, urls, tmp_path=None, **kw):
    return await run_ingestion(conn, client, [Candidate(u, u.rsplit("/", 1)[-1]) for u in urls],
                               source_code="TN_GOV_PORTAL", data_dir=tmp_path, **kw)


@pytest.mark.db
async def test_successful_ingestion_records_full_provenance(conn, site, client, clean_docs, tmp_path):
    site.routes["/docs/go12.pdf"] = pdf_response()
    rep = await ingest(conn, client, [f"{BASE}/go12.pdf"], tmp_path, doc_type="GO", department_code="EDUC")
    assert rep["counts"] == {"stored": 1} and rep["failures"] == []
    row = await conn.fetchrow("SELECT * FROM documents.document WHERE source_url=$1", f"{BASE}/go12.pdf")
    assert row["file_hash"] == hashlib.sha256(GO_PDF).hexdigest()
    assert row["document_type"] == "GO" and row["status"] == "active" and row["language"] == "en"
    assert row["extraction_status"] == "ok" and row["page_count"] == 2 and row["http_status"] == 200
    assert row["verification_status"] == "unverified"             # origin is official; content not verified
    assert row["retrieved_at"] is not None and row["source_document_id"] == "go12.pdf"
    assert row["publication_date"] is None                          # never invented
    assert row["department_id"] is not None and "Government Order" in row["full_text"]
    assert (tmp_path / row["file_path"]).read_bytes() == GO_PDF
    chunks = await conn.fetch("SELECT * FROM documents.document_chunk WHERE document_id=$1 ORDER BY chunk_number", row["document_id"])
    assert [c["page_number"] for c in chunks] == [1, 2] and all(c["embedding"] is None for c in chunks)
    src = await conn.fetchval("SELECT source_code FROM system.source_registry WHERE source_id=$1", row["source_id"])
    assert src == "TN_GOV_PORTAL"
    stages = {r["stage"] for r in await conn.fetch("SELECT stage FROM system.ingestion_log WHERE run_id=$1", row["ingestion_run_id"])}
    assert {"download", "extract", "chunk", "store"} <= stages


@pytest.mark.db
async def test_duplicates_are_detected_and_changed_files_supersede(conn, site, client, clean_docs):
    site.routes["/docs/dup.pdf"] = pdf_response()
    first = await ingest(conn, client, [f"{BASE}/dup.pdf"])
    again = await ingest(conn, client, [f"{BASE}/dup.pdf"])
    assert first["counts"] == {"stored": 1} and again["counts"] == {"duplicate": 1}
    assert await conn.fetchval("SELECT count(*) FROM documents.document WHERE source_url=$1", f"{BASE}/dup.pdf") == 1

    site.routes["/docs/dup.pdf"] = pdf_response(make_pdf("Revised order text with new wording for the same URL."))
    changed = await ingest(conn, client, [f"{BASE}/dup.pdf"])
    assert changed["counts"] == {"stored": 1}
    st = [r["status"] for r in await conn.fetch("SELECT status FROM documents.document WHERE source_url=$1 ORDER BY created_at", f"{BASE}/dup.pdf")]
    assert st == ["superseded", "active"]            # history kept, only the latest is active


@pytest.mark.db
async def test_failures_are_isolated_reported_and_logged(conn, site, client, clean_docs):
    site.routes["/docs/ok.pdf"] = pdf_response(make_pdf("A valid document that should still be ingested despite others failing."))
    site.routes["/docs/page.pdf"] = httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"})
    rep = await ingest(conn, client, [f"{BASE}/missing.pdf", f"{BASE}/page.pdf", "https://evil.example.com/e.pdf", f"{BASE}/ok.pdf"])
    assert rep["counts"] == {"failed": 3, "stored": 1}
    assert {f["stage"] for f in rep["failures"]} == {"download", "validate"}
    assert await conn.fetchval("SELECT count(*) FROM documents.document WHERE source_url LIKE 'https://%tn.gov.in/docs/%'") == 1
    logged = await conn.fetch("SELECT url, stage, detail FROM system.ingestion_log WHERE run_id=$1 AND status='failed'", uuid.UUID(rep["run_id"]))
    assert len(logged) == 3 and all(r["detail"] for r in logged)


@pytest.mark.db
async def test_image_only_and_corrupt_pdfs_are_recorded_but_not_searchable(conn, site, client, clean_docs):
    blank = pymupdf.open()
    blank.new_page()
    blank_bytes = blank.tobytes()
    blank.close()
    site.routes["/docs/scan.pdf"] = pdf_response(blank_bytes)
    site.routes["/docs/corrupt.pdf"] = pdf_response(b"%PDF-1.4 this is not really a pdf at all")
    rep = await ingest(conn, client, [f"{BASE}/scan.pdf", f"{BASE}/corrupt.pdf"])
    assert rep["counts"] == {"stored_empty": 1, "stored_failed": 1}
    rows = {r["source_document_id"]: r for r in await conn.fetch("SELECT * FROM documents.document WHERE source_url LIKE 'https://%tn.gov.in/docs/%'")}
    assert rows["scan.pdf"]["extraction_status"] == "empty" and "OCR" in rows["scan.pdf"]["extraction_error"]
    assert rows["corrupt.pdf"]["extraction_status"] == "failed"
    assert await conn.fetchval("SELECT count(*) FROM documents.document_chunk WHERE document_id = ANY($1)", [r["document_id"] for r in rows.values()]) == 0


def test_unreadable_text_layer_is_not_reported_as_ok():
    from etl.extractors.pdf import extract_pdf, readable_share

    junk = make_pdf("! ! ! !! !!! . . , , ; ; ! ! ! ! ! !! . . . , , , ; ; ; ! ! ! ! ! !")
    ext = extract_pdf(junk)
    assert ext.status == "empty" and "unreadable" in ext.error
    assert extract_pdf(GO_PDF).status == "ok"
    assert readable_share(["abc 123 !!"]) == pytest.approx(6 / 8)
    assert readable_share([""]) == 0.0


@pytest.mark.db
async def test_unapproved_source_and_bad_arguments_are_refused(conn, client):
    with pytest.raises(ValueError, match="approved official source"):
        await run_ingestion(conn, client, [], source_code="TN_TNAU_REF")        # trusted_open, not official
    with pytest.raises(ValueError, match="not an approved"):
        await run_ingestion(conn, client, [], source_code="NOPE")
    with pytest.raises(ValueError, match="doc_type"):
        await run_ingestion(conn, client, [], source_code="TN_GOV_PORTAL", doc_type="Rumour")
    with pytest.raises(ValueError, match="department_code"):
        await run_ingestion(conn, client, [], source_code="TN_GOV_PORTAL", department_code="NOPE")


@pytest.mark.db
async def test_limit_is_honoured(conn, site, client, clean_docs):
    for i in range(3):
        site.routes[f"/docs/l{i}.pdf"] = pdf_response(make_pdf(f"Document number {i} with enough text to be extracted properly."))
    rep = await ingest(conn, client, [f"{BASE}/l{i}.pdf" for i in range(3)], limit=2)
    assert rep["attempted"] == 2 and rep["counts"] == {"stored": 2}
