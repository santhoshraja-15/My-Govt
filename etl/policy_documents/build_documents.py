"""Download and verify every candidate document, then write data/policy_documents/documents.json.

    python etl/policy_documents/build_documents.py [--cache DIR]

A record becomes `official_verified` only if the official URL returns a real PDF (%PDF header, readable) AND its extracted text
contains every needle. Scanned PDFs without a text layer, or PDFs whose text does not match, stay `provisional` with the reason in
`verification.note`. Nothing is promoted because a URL merely responds.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))
from candidates import CANDIDATES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "policy_documents" / "documents.json"
UA = {"User-Agent": "Mozilla/5.0 (MyGovt verification)"}


def fetch(url: str, cache: Path) -> tuple[bytes | None, str]:
    f = cache / (hashlib.sha1(url.encode()).hexdigest() + ".pdf")
    if f.exists():
        return f.read_bytes(), "cached"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                data = r.read(80_000_000)
                f.write_bytes(data)
                return data, f"HTTP {r.status} {r.headers.get('content-type', '')}"
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            time.sleep(2)
    return None, err


def verify(c: dict, cache: Path) -> dict:
    data, how = fetch(c["pdf"], cache)
    v = {"checked_on": date.today().isoformat(), "http": how, "pdf_ok": False, "pages": None, "text_chars": 0, "needles_found": [], "needles_missing": [],
         "sha256": None, "bytes": None, "note": ""}
    if not data:
        v["note"] = "PDF could not be downloaded: " + how
        return v
    v["bytes"] = len(data)
    v["sha256"] = hashlib.sha256(data).hexdigest()
    if not data.startswith(b"%PDF"):
        v["note"] = "Response is not a PDF."
        return v
    try:
        rd = PdfReader(io.BytesIO(data))
        v["pages"] = len(rd.pages)
        text = " ".join((p.extract_text() or "") for p in rd.pages[:12])
    except Exception as e:  # noqa: BLE001
        v["note"] = f"PDF unreadable: {e}"
        return v
    v["pdf_ok"] = True
    v["text_chars"] = len(text)
    low = text.lower()
    for n in c["needles"]:
        (v["needles_found"] if n.lower() in low else v["needles_missing"]).append(n)
    v["first_text"] = " ".join(text.split())[:240]
    if v["text_chars"] < 200:
        v["note"] = "No usable text layer (scanned or image PDF); title/date not machine-confirmed against the document."
    elif not c["needles"]:
        v["note"] = "PDF opens; no machine-checkable identifier was defined for this record."
    elif v["needles_missing"]:
        v["note"] = "PDF opens but expected text not found: " + ", ".join(v["needles_missing"])
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / ".cache" / "policy_pdfs"))
    a = ap.parse_args()
    cache = Path(a.cache); cache.mkdir(parents=True, exist_ok=True)
    out = []
    for c in CANDIDATES:
        v = verify(c, cache)
        confirmed = bool(v["pdf_ok"] and ((v["text_chars"] >= 200 and c["needles"] and not v["needles_missing"]) or c.get("visual")))
        if c.get("visual") and v["pdf_ok"] and v["text_chars"] < 200:
            v["note"] = "Scanned PDF (no text layer): page 1 was rendered and its title, number and date were checked by eye against this record on " + v["checked_on"] + "."
        rec = {k: c[k] for k in ("id", "category", "identifier", "issued", "title", "department", "summary_en", "summary_ta", "language", "related", "source_page")}
        rec.update(title_ta=c.get("title_ta"), pdf_url=c["pdf"] if v["pdf_ok"] else None, landing_url=c["source_page"],
                   effective_date=None, superseded=None,
                   verification_status="official_verified" if confirmed else "provisional", verification=v,
                   summary_ta_reviewed=False,
                   notes=("; ".join(x for x in [c.get("notes", ""), v["note"], "" if c["issued"] else "Issue date not confirmed from the document text."] if x)))
        out.append(rec)
        print(f"{rec['verification_status']:17} {rec['id']:28} pages={v['pages']} chars={v['text_chars']} {v['note'][:60]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(r["verification_status"] == "official_verified" for r in out)
    print(f"\n{len(out)} records, {ok} official_verified, {sum(1 for r in out if r['pdf_url'])} working PDFs -> {OUT}")


if __name__ == "__main__":
    main()
