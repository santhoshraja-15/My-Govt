"""HTTP connector for approved official sources: allow-list, robots.txt, validated downloads, retries."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

USER_AGENT = "MyGovtBot/1.0 (+https://github.com/santhoshraja-15/My-Govt; citizen-information indexer)"
MAX_BYTES = 30 * 1024 * 1024


class IngestError(Exception):
    """A document could not be ingested; `stage` names the pipeline stage that failed."""

    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage, self.message = stage, message


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str


@dataclass
class Downloaded:
    url: str
    content: bytes
    content_type: str
    status: int
    sha256: str


def registered_hosts(source_urls: list[str]) -> set[str]:
    """Allow-list from source_registry URLs: 'www.tn.gov.in' -> 'tn.gov.in' (subdomains allowed)."""
    return {(urlsplit(u).hostname or "").removeprefix("www.") for u in source_urls if u}


def host_allowed(url: str, allowed: set[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return bool(host) and any(host == a or host.endswith("." + a) for a in allowed if a)


class TransientHTTP(Exception):
    pass


def _is_transient(e: BaseException) -> bool:
    return isinstance(e, (TransientHTTP, httpx.TransportError))


async def robots_allows(client: httpx.AsyncClient, url: str, user_agent: str = USER_AGENT) -> bool:
    """True if robots.txt permits the fetch. An unreachable robots.txt (404/errors) counts as allowed."""
    parts = urlsplit(url)
    try:
        r = await client.get(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=10)
    except httpx.HTTPError:
        return True
    if r.status_code != 200:
        return True
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    return rp.can_fetch(user_agent, url)


@retry(retry=retry_if_exception(_is_transient), stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.2, max=2), reraise=True)
async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    r = await client.get(url, follow_redirects=True, timeout=30)
    if r.status_code in (429, 500, 502, 503, 504):
        raise TransientHTTP(f"HTTP {r.status_code}")
    return r


async def discover_links(client: httpx.AsyncClient, page_url: str, allowed: set[str]) -> list[Candidate]:
    """PDF links on an approved page (only links whose host is also on the allow-list)."""
    try:
        r = await _get(client, page_url)
    except (TransientHTTP, httpx.HTTPError) as e:
        raise IngestError("discover", f"{type(e).__name__}: {e}") from e
    if r.status_code != 200:
        raise IngestError("discover", f"listing page returned HTTP {r.status_code}")
    out: dict[str, Candidate] = {}
    pattern = r"<a[^>]+href=[\"']([^\"']+\.pdf)[\"'][^>]*>(.*?)</a>"
    for m in re.finditer(pattern, r.text, re.I | re.S):
        url = urljoin(str(r.url), m.group(1).strip())
        if not host_allowed(url, allowed):
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        out.setdefault(url, Candidate(url, text or url.rsplit("/", 1)[-1]))
    return list(out.values())


async def download(client: httpx.AsyncClient, url: str, allowed: set[str], max_bytes: int = MAX_BYTES) -> Downloaded:
    """Fetch and validate one document. Raises IngestError(stage, reason) on any rejection."""
    if not host_allowed(url, allowed):
        raise IngestError("validate", f"host not on the approved-source allow-list: {urlsplit(url).hostname}")
    if not await robots_allows(client, url):
        raise IngestError("robots", "disallowed by robots.txt")
    try:
        r = await _get(client, url)
    except (TransientHTTP, httpx.HTTPError) as e:
        raise IngestError("download", f"{type(e).__name__}: {e}") from e
    if not host_allowed(str(r.url), allowed):      # checked first: never trust anything served off-list
        raise IngestError("validate", f"redirected outside the allow-list: {urlsplit(str(r.url)).hostname}")
    if r.status_code != 200:
        raise IngestError("download", f"HTTP {r.status_code}")
    body = r.content
    if len(body) > max_bytes:
        raise IngestError("validate", f"file too large ({len(body)} bytes > {max_bytes})")
    if not body.startswith(b"%PDF-"):
        raise IngestError("validate", f"not a PDF (content-type {r.headers.get('content-type', '?')})")
    return Downloaded(str(r.url), body, r.headers.get("content-type", "application/pdf"), r.status_code,
                      hashlib.sha256(body).hexdigest())
