"""Generate database/seeds/003_content.sql from the curated content modules and the verified policy-document register.

    python etl/content/generate_seed.py

Inputs : data/policy_documents/documents.json   (etl/policy_documents/build_documents.py)
         data/content/esevai_service_list_2023-04-10.json  (rows copied from the official e-Sevai service list)
         etl/content/schemes_content.py, etl/content/services_content.py
Output : database/seeds/003_content.sql  - idempotent (INSERT .. ON CONFLICT DO UPDATE; child rows are replaced).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from schemes_content import CHECK, SCHEMES  # noqa: E402
from services_content import LIST_URL, SERVICES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CHECKED = CHECK
OUT = ROOT / "database" / "seeds" / "003_content.sql"
ROWS = {r[0]: r for r in json.loads((ROOT / "data" / "content" / "esevai_service_list_2023-04-10.json").read_text(encoding="utf-8"))}
DOCS = json.loads((ROOT / "data" / "policy_documents" / "documents.json").read_text(encoding="utf-8"))


def q(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def j(v) -> str:
    return q(json.dumps(v, ensure_ascii=False)) + "::jsonb"


SOURCE_BY_DEPT = {1: "TN_REVENUE", 5: "TN_WELFARE", 8: "TN_RDPR"}


def source_sql(dept_id) -> str:
    return f"(SELECT source_id FROM system.source_registry WHERE source_code = {q(SOURCE_BY_DEPT.get(dept_id, 'TN_GOV_PORTAL'))})"


def split_docs(text: str) -> list[str]:
    parts = [p.strip(" .;") for p in re.split(r"\s*\d+\.\s+", " " + text.strip().strip('"')) if p.strip(" .;")]
    return parts


def timeline(t: str) -> str | None:
    t = (t or "").strip()
    if t in ("", "-", "NA"):
        return None
    m = re.match(r"0?(\d+)\s*days?", t, re.I)
    return f"{int(m.group(1))} days" if m else t


def evidence(ev: dict) -> dict:
    return {k: {"url": u, "confirmed": True, "checked_on": CHECKED, "what": w} for k, (u, w) in ev.items()}


def documents_sql() -> list[str]:
    out = ["-- ── Policy documents (official PDFs, verified by etl/policy_documents/build_documents.py) ──",
           "SELECT set_config('app.verification_reason', 'policy document catalogue load: PDF downloaded from the official site and matched (text or page-1 visual check)', false);"]
    for d in DOCS:
        v = d["verification"]
        legal = None
        if d["category"] == "act":
            legal = "Published as an Act in the Tamil Nadu Government Gazette Extraordinary (Part IV Section 2); commencement date not confirmed"
        elif d["category"] == "notification":
            legal = "Published in the Tamil Nadu Government Gazette Extraordinary"
        ref = f"{d['pdf_url']}" if d["pdf_url"] else None
        method = ("text match on the official PDF" if v["text_chars"] >= 200 else "page-1 visual check of a scanned PDF") if d["verification_status"] == "official_verified" else None
        out.append(
            "INSERT INTO documents.policy_document (doc_code, category, identifier, title, title_ta, issuing_authority, issued_on, summary_en, summary_ta, summary_ta_reviewed, "
            "language, related_topics, source_page_url, pdf_url, pdf_sha256, pdf_pages, legal_status, verification_status, source_document_ref, verification_method, last_checked_on, notes) VALUES ("
            f"{q(d['id'])}, {q(d['category'])}, {q(d['identifier'])}, {q(d['title'])}, {q(d['title_ta'])}, {q(d['department'])}, {q(d['issued'])}, {q(d['summary_en'])}, {q(d['summary_ta'])}, FALSE, "
            f"{q(d['language'])}, ARRAY[{', '.join(q(x) for x in d['related'])}]::text[], {q(d['source_page'])}, {q(d['pdf_url'])}, {q(v['sha256'])}, {q(v['pages'])}, {q(legal)}, "
            f"{q(d['verification_status'])}, {q(ref)}, {q(method)}, {q(v['checked_on'])}, {q(d['notes'] or None)}) "
            "ON CONFLICT (doc_code) DO UPDATE SET category = EXCLUDED.category, identifier = EXCLUDED.identifier, title = EXCLUDED.title, issuing_authority = EXCLUDED.issuing_authority, "
            "issued_on = EXCLUDED.issued_on, summary_en = EXCLUDED.summary_en, summary_ta = EXCLUDED.summary_ta, language = EXCLUDED.language, related_topics = EXCLUDED.related_topics, "
            "source_page_url = EXCLUDED.source_page_url, pdf_url = EXCLUDED.pdf_url, pdf_sha256 = EXCLUDED.pdf_sha256, pdf_pages = EXCLUDED.pdf_pages, legal_status = EXCLUDED.legal_status, "
            "verification_status = EXCLUDED.verification_status, source_document_ref = EXCLUDED.source_document_ref, verification_method = EXCLUDED.verification_method, "
            "last_checked_on = EXCLUDED.last_checked_on, notes = EXCLUDED.notes;")
    return out


def schemes_sql() -> list[str]:
    out = ["", "-- ── Schemes: content completeness (project reference + official pages read 2026-10-20; see etl/content/schemes_content.py) ──",
           "SELECT set_config('app.verification_reason', 'content load: eligibility, benefits and documents added; record stays provisional pending official verification', false);"]
    for s in SCHEMES:
        code = s["code"]
        srcs = [{"url": u, "label": l} for u, l in s["sources"]]
        cols = ("scheme_code, scheme_name, name_ta, short_description, full_description, short_description_ta, scheme_level, department_id, category, benefits_summary, application_url, official_url, "
                "status, verification_status, source_id, implementing_department, purpose, eligibility_points, exclusion_points, application_steps, how_to_apply_note, source_urls, last_checked_on, content_notes, field_evidence")
        vals = (f"{q(code)}, {q(s['name'])}, {q(s['name_ta'])}, {q(s['purpose'])}, {q(s['desc'])}, {q(s['desc_ta'])}, {q(s['level'])}, {q(s['dept_id'])}, {q(s['category'])}, {q(s['benefits_summary'])}, "
                f"{q(s['apply_url'])}, {q(s['official_url'])}, 'active', 'provisional', {source_sql(s['dept_id'])}, {q(s['dept_text'])}, {q(s['purpose'])}, {j(s['eligibility'])}, {j(s['exclusions'])}, {j(s['steps'])}, {q(s['how_note'])}, "
                f"{j(srcs)}, {q(CHECKED)}, {q(s['notes'])}, {j(evidence(s['ev']))}")
        update = ("short_description = EXCLUDED.short_description, full_description = EXCLUDED.full_description, short_description_ta = EXCLUDED.short_description_ta, benefits_summary = EXCLUDED.benefits_summary, "
                  "application_url = EXCLUDED.application_url, official_url = EXCLUDED.official_url, implementing_department = EXCLUDED.implementing_department, purpose = EXCLUDED.purpose, "
                  "eligibility_points = EXCLUDED.eligibility_points, exclusion_points = EXCLUDED.exclusion_points, application_steps = EXCLUDED.application_steps, how_to_apply_note = EXCLUDED.how_to_apply_note, "
                  "source_urls = EXCLUDED.source_urls, last_checked_on = EXCLUDED.last_checked_on, content_notes = EXCLUDED.content_notes, field_evidence = EXCLUDED.field_evidence")
        out.append(f"INSERT INTO schemes.scheme ({cols}) VALUES ({vals}) ON CONFLICT (scheme_code) DO UPDATE SET {update};")
        sid = f"(SELECT scheme_id FROM schemes.scheme WHERE scheme_code = {q(code)})"
        out.append(f"DELETE FROM schemes.benefit WHERE scheme_id = {sid};")
        for b in s["benefits"]:
            out.append("INSERT INTO schemes.benefit (scheme_id, benefit_type, description, amount, currency, frequency, conditions, amount_status) VALUES "
                       f"({sid}, {q(b['type'])}, {q(b['description'])}, {q(b['amount'])}, 'INR', {q(b['frequency'])}, {q(b['conditions'])}, {q(b['amount_status'])});")
        out.append(f"DELETE FROM schemes.document_requirement WHERE scheme_id = {sid};")
        for d in s["docs"]:
            out.append("INSERT INTO schemes.document_requirement (scheme_id, document_name, mandatory, description, requirement_level) VALUES "
                       f"({sid}, {q(d['name'])}, {q(d['level'] == 'required')}, {q(d['note'])}, {q(d['level'])});")
    return out


def services_sql() -> list[str]:
    out = ["", f"-- ── Services: content completeness (official e-Sevai service list, last updated 10/04/2023; {LIST_URL}) ──",
           "SELECT set_config('app.verification_reason', 'content load: fees, timelines and documents from the e-Sevai service list (2023); record stays provisional', false);"]
    for s in SERVICES:
        rows = [ROWS[r] for r in ([s["row"]] if isinstance(s["row"], str) else (s["row"] or []))]
        main = rows[0] if rows else None
        fee = charge = None
        proc = None
        fee_status = "not_listed"
        fee_note = s["fee_override"]
        if main:
            fee_status = "listed_official_2023"
            if not fee_note or True:
                try:
                    fee = float(main[5])
                    charge = float(main[6])
                except ValueError:
                    fee = charge = None
            proc = timeline(main[4])
            if s["fee_override"]:
                fee = charge = None          # several listings with different charges: described in the note instead
            else:
                fee_note = (f"Per the official e-Sevai service list (last updated 10 Apr 2023): application fee Rs.{main[5]}, e-Sevai service-centre charge Rs.{main[6]}. "
                            "This list is more than three years old - confirm on the live portal or payment screen.")
        proc_note = ("Stipulated timeline as listed on the e-Sevai service list (last updated 10 Apr 2023); confirm the current timeline." if proc
                     else "Not confirmed from an official source.")
        docs = []
        if main and main[7] not in ("", "NA"):
            docs = [(d, "required", "Listed on the official e-Sevai service list (2023)") for d in split_docs(main[7])]
        elif s["docs"]:
            docs = [(t[0], t[1], (t[2] if len(t) > 2 else None)) for t in s["docs"]]
        evid = {}
        if main:
            evid["fee"] = (LIST_URL, f"e-Sevai list row {main[0]}")
            if proc:
                evid["processing_time"] = (LIST_URL, f"e-Sevai list row {main[0]}")
            if main[7] not in ("", "NA"):
                evid["documents"] = (LIST_URL, f"e-Sevai list row {main[0]}")
        srcs = [{"url": u, "label": l} for u, l in s["sources"]]
        if main and not srcs:
            srcs = [{"url": LIST_URL, "label": f"e-Sevai Service List: row {main[0]}"}]
        how = s["how"] or ("Apply at an e-Sevai centre: the official list shows this service as operator-assisted. The list's link for applying is the e-Sevai portal." if main and main[3] == "Operator" else None)
        steps = ["Open the e-Sevai portal or visit an e-Sevai centre." if main else "Contact the responsible office.", "Choose the service and give the details requested.",
                 "Upload or hand over the documents shown on this page.", "Pay any fee shown on the payment screen and keep the acknowledgement."] if main else []
        cols = ("service_code, service_name, name_ta, department_id, category, description, description_ta, application_url, official_url, government_fee, service_charge, processing_time, status, "
                "verification_status, source_id, responsible_department, eligibility_points, application_steps, how_to_apply, applicable_rules, source_urls, last_checked_on, content_notes, fee_note, "
                "processing_time_note, fee_status, field_evidence")
        vals = (f"{q(s['code'])}, {q(s['name'])}, {q(s['name_ta'])}, {q(s['dept_id'])}, {q(s['category'])}, {q(s['desc'])}, {q(s['desc_ta'])}, {q(s['url'])}, {q(s['url'])}, {q(fee)}, {q(charge)}, "
                f"{q(proc)}, 'active', 'provisional', {source_sql(s['dept_id'])}, {q(s['dept'])}, {j(s['eligibility'])}, {j(steps)}, {q(how)}, {q(s['rules'])}, {j(srcs)}, {q(CHECKED)}, {q(s['notes'])}, {q(fee_note)}, "
                f"{q(proc_note)}, {q(fee_status)}, {j(evidence(evid))}")
        update = ("description = EXCLUDED.description, description_ta = EXCLUDED.description_ta, application_url = EXCLUDED.application_url, official_url = EXCLUDED.official_url, "
                  "government_fee = EXCLUDED.government_fee, service_charge = EXCLUDED.service_charge, processing_time = EXCLUDED.processing_time, responsible_department = EXCLUDED.responsible_department, "
                  "eligibility_points = EXCLUDED.eligibility_points, application_steps = EXCLUDED.application_steps, how_to_apply = EXCLUDED.how_to_apply, applicable_rules = EXCLUDED.applicable_rules, "
                  "source_urls = EXCLUDED.source_urls, last_checked_on = EXCLUDED.last_checked_on, content_notes = EXCLUDED.content_notes, fee_note = EXCLUDED.fee_note, "
                  "processing_time_note = EXCLUDED.processing_time_note, fee_status = EXCLUDED.fee_status, field_evidence = EXCLUDED.field_evidence")
        out.append(f"INSERT INTO services.service ({cols}) VALUES ({vals}) ON CONFLICT (service_code, department_id) DO UPDATE SET {update};")
        sid = f"(SELECT service_id FROM services.service WHERE service_code = {q(s['code'])})"
        out.append(f"DELETE FROM services.service_requirement WHERE service_id = {sid};")
        for name, level, note in docs:
            out.append("INSERT INTO services.service_requirement (service_id, document_name, mandatory, description, requirement_level) VALUES "
                       f"({sid}, {q(name)}, {q(level == 'required')}, {q(note)}, {q(level)});")
    return out


def main() -> None:
    lines = ["-- =====================================================================",
             "-- 003_content.sql - GENERATED by etl/content/generate_seed.py. Do not edit by hand.",
             "-- Policy-document catalogue, scheme and service content. Idempotent.",
             "-- All scheme and service rows stay 'provisional'; policy documents are 'official_verified' only where the official PDF was matched.",
             "-- ====================================================================="]
    lines += documents_sql() + schemes_sql() + services_sql()
    lines += ["", "SELECT set_config('app.verification_reason', '', false);", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines): {len(DOCS)} documents, {len(SCHEMES)} schemes, {len(SERVICES)} services")


if __name__ == "__main__":
    main()
