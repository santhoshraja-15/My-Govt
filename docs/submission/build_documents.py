"""Builds MyGovt_Project_Report.docx and MyGovt_Final_PPT.pptx for BCSE302P from real project artefacts.

Inputs (all produced from the real project, none typed in by hand):
  * database/schema/001_schema.sql        -> CREATE TABLE statements
  * the scratch database (--dsn)          -> INSERT statements built from real rows, catalog tables (PK/FK), live counts
  * sql_evidence.json                     -> statements + outputs recorded by run_sql_evidence.py
  * images/*.png                          -> application screenshots (frontend/audit/submission_shots.js)
  * docs/audit/*.csv                      -> testing results

    python build_documents.py --dsn postgresql://postgres@localhost:5432/mygovt_dev_report
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from pathlib import Path

import asyncpg
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt as PPt

NL2 = chr(10) * 2
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMG = HERE / "images"
PH_NAMES = "[STUDENT NAME 1 – to be filled]   [STUDENT NAME 2 – to be filled]"
PH_REGS = "[REGISTER NO. 1 – to be filled]   [REGISTER NO. 2 – to be filled]"
PH_FACULTY = "[FACULTY NAME – to be filled]"
TITLE = "MyGovt – AI-Powered Tamil Nadu Citizen Services Platform"
SUB = "A PostgreSQL / PostGIS / pgvector database system for schemes, services and complaint management"
COURSE = "BCSE302L – Database Systems  (Lab: BCSE302P)"

CORE = ["administration.department", "administration.authority", "administration.officer", "identity.app_user", "identity.citizen",
        "schemes.scheme", "schemes.eligibility_rule", "services.service", "complaints.complaint_category", "complaints.complaint",
        "complaints.complaint_history", "audit.audit_log"]


# ──────────────────────────── data gathering ────────────────────────────
def ddl_for(sql_text: str, table: str) -> str:
    m = re.search(rf"^CREATE TABLE {re.escape(table)}\s*\(.*?^\);", sql_text, re.S | re.M)
    return m.group(0).strip() if m else f"-- {table}: definition not found"


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return "'" + str(v).replace("'", "''") + "'"


async def gather(dsn: str) -> dict:
    c = await asyncpg.connect(dsn)
    d: dict = {}
    d["version"] = (await c.fetchval("select version()")).split(",")[0]
    d["counts"] = {t: await c.fetchval(f"select count(*) from {t}") for t in CORE}
    d["totals"] = dict(await c.fetchrow("""select
        (select count(*) from information_schema.tables where table_type='BASE TABLE' and table_schema not in ('pg_catalog','information_schema','public')) as tables,
        (select count(*) from information_schema.columns c join information_schema.tables t using (table_schema, table_name) where t.table_type='BASE TABLE' and table_schema not in ('pg_catalog','information_schema','public')) as columns,
        (select count(*) from pg_constraint co join pg_namespace n on n.oid=co.connamespace where co.contype='f' and n.nspname not in ('pg_catalog','public')) as fks,
        (select count(*) from pg_trigger t join pg_class cl on cl.oid=t.tgrelid join pg_namespace n on n.oid=cl.relnamespace where not t.tgisinternal and n.nspname not in ('pg_catalog','public')) as triggers"""))
    d["schema_tables"] = [dict(r) for r in await c.fetch("select table_schema as s, count(*) as n from information_schema.tables where table_type='BASE TABLE' and table_schema not in ('pg_catalog','information_schema','public') group by 1 order by 1")]
    attrs = {}
    for t in CORE:
        s, n = t.split(".")
        rows = await c.fetch("""select a.attname as col, format_type(a.atttypid, a.atttypmod) as typ, a.attnotnull as nn
            from pg_attribute a where a.attrelid = $1::regclass and a.attnum > 0 and not a.attisdropped order by a.attnum""", t)
        pk = {r[0] for r in await c.fetch("select a.attname from pg_index i join pg_attribute a on a.attrelid=i.indrelid and a.attnum = any(i.indkey) where i.indrelid=$1::regclass and i.indisprimary", t)}
        fk = {}
        for r in await c.fetch("select a.attname as col, confrelid::regclass::text as ref from pg_constraint co join pg_attribute a on a.attrelid=co.conrelid and a.attnum = any(co.conkey) where co.conrelid=$1::regclass and co.contype='f'", t):
            fk[r["col"]] = r["ref"]
        uq = {r[0] for r in await c.fetch("select a.attname from pg_constraint co join pg_attribute a on a.attrelid=co.conrelid and a.attnum = any(co.conkey) where co.conrelid=$1::regclass and co.contype='u' and array_length(co.conkey,1)=1", t)}
        attrs[t] = [{"col": r["col"], "type": r["typ"], "nn": r["nn"], "pk": r["col"] in pk, "fk": fk.get(r["col"]), "uq": r["col"] in uq} for r in rows]
    d["attrs"] = attrs
    d["fk_edges"] = [(r["f"], r["t"], r["cols"]) for r in await c.fetch("""select conrelid::regclass::text as f, confrelid::regclass::text as t,
        (select string_agg(attname, ', ') from pg_attribute where attrelid=conrelid and attnum = any(conkey)) as cols
        from pg_constraint where contype='f' and conrelid::regclass::text = any($1::text[]) and confrelid::regclass::text = any($1::text[]) order by 1,2""", CORE)]
    # real rows → INSERT statements (selected columns keep them readable)
    inserts = []
    for table, cols, order, lim, where in [
        ("administration.department", ["department_code", "department_name", "status"], "department_id", 3, ""),
        ("complaints.complaint_category", ["category_code", "category_name", "default_sla_hours"], "category_id", 3, ""),
        ("schemes.scheme", ["scheme_code", "scheme_name", "scheme_level", "status"], "scheme_name", 2, ""),
        ("services.service", ["service_code", "service_name", "category"], "service_name", 2, ""),
        ("schemes.eligibility_rule", ["rule_type", "operator", "value_json"], "rule_id", 2, ""),
    ]:
        try:
            recs = await c.fetch(f"select {', '.join(cols)} from {table} {where} order by {order} limit {lim}")
        except Exception:  # noqa: BLE001 – a column name differs: skip the sample rather than invent it
            continue
        for r in recs:
            vals = [lit(r[k] if not isinstance(r[k], (dict, list)) else json.dumps(r[k])) for k in cols]
            inserts.append(f"INSERT INTO {table} ({', '.join(cols)})\nVALUES ({', '.join(vals)});")
    d["inserts"] = inserts
    await c.close()
    return d


# ──────────────────────────── docx helpers ────────────────────────────
NAVY = RGBColor(0x1E, 0x3A, 0x8A)


def shade(cell_or_par, hex_fill: str):
    el = cell_or_par._tc.get_or_add_tcPr() if hasattr(cell_or_par, "_tc") else cell_or_par._p.get_or_add_pPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_fill)
    el.append(sh)


def set_font(run, name="Calibri", size=11, bold=None, color=None, italic=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None: run.bold = bold
    if italic is not None: run.italic = italic
    if color is not None: run.font.color.rgb = color


class Report:
    def __init__(self):
        self.doc = Document()
        s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        s.left_margin = s.right_margin = Cm(2.54); s.top_margin = s.bottom_margin = Cm(2.3)
        st = self.doc.styles["Normal"]
        st.font.name = "Calibri"; st.font.size = Pt(11)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.25
        for name, size, before, after in [("Heading 1", 18, 20, 8), ("Heading 2", 14, 14, 6), ("Heading 3", 12, 10, 4)]:
            h = self.doc.styles[name]
            h.font.name = "Calibri"; h.font.size = Pt(size); h.font.bold = True; h.font.color.rgb = NAVY
            h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri"); h.element.rPr.rFonts.set(qn("w:ascii"), "Calibri"); h.element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
            h.paragraph_format.space_before = Pt(before); h.paragraph_format.space_after = Pt(after); h.paragraph_format.keep_with_next = True
        self.fig = 0
        self.tab = 0
        self._footer(s)

    def _footer(self, section):
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("MyGovt – BCSE302P Database Systems Lab Project Report   |   Page ")
        set_font(r, size=9, color=RGBColor(0x64, 0x74, 0x8B))
        r2 = p.add_run()
        for t, txt in (("begin", None), (None, "PAGE"), ("end", None)):
            if t:
                f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), t); r2._r.append(f)
            else:
                i = OxmlElement("w:instrText"); i.set(qn("xml:space"), "preserve"); i.text = txt; r2._r.append(i)
        set_font(r2, size=9, color=RGBColor(0x64, 0x74, 0x8B))

    def h(self, text, level=1):
        return self.doc.add_heading(text, level)

    def p(self, text="", bold=False, italic=False, size=11, align=None, color=None, after=None):
        para = self.doc.add_paragraph()
        r = para.add_run(text); set_font(r, size=size, bold=bold, italic=italic, color=color)
        if align: para.alignment = align
        else: para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if after is not None: para.paragraph_format.space_after = Pt(after)
        return para

    def bullets(self, items, style="List Bullet"):
        for it in items:
            para = self.doc.add_paragraph(style=style)
            if isinstance(it, tuple):
                r = para.add_run(it[0]); set_font(r, bold=True)
                r = para.add_run(it[1]); set_font(r)
            else:
                set_font(para.add_run(it))
            para.paragraph_format.space_after = Pt(3)

    def code(self, text, size=8.5):
        for line_group in [text.rstrip("\n")]:
            para = self.doc.add_paragraph()
            para.paragraph_format.space_after = Pt(8); para.paragraph_format.line_spacing = 1.0
            para.paragraph_format.left_indent = Cm(0.2)
            shade(para, "F1F5F9")
            lines = line_group.split("\n")
            for i, ln in enumerate(lines):
                r = para.add_run(ln); set_font(r, "Consolas", size)
                if i < len(lines) - 1: r.add_break()
        return

    def output(self, text, size=8):
        para = self.doc.add_paragraph()
        para.paragraph_format.space_after = Pt(10); para.paragraph_format.line_spacing = 1.0
        para.paragraph_format.left_indent = Cm(0.2)
        shade(para, "ECFDF5")
        lines = text.rstrip("\n").split("\n")
        for i, ln in enumerate(lines[:30]):
            r = para.add_run(ln[:118]); set_font(r, "Consolas", size, color=RGBColor(0x06, 0x4E, 0x3B))
            if i < min(len(lines), 30) - 1: r.add_break()
        if len(lines) > 30:
            para.add_run().add_break(); set_font(para.add_run(f"… ({len(lines) - 30} more lines omitted)"), "Consolas", size)

    def table(self, header, rows, widths=None, size=9.5, caption=None):
        if caption:
            self.tab += 1
            para = self.p(f"Table {self.tab}: {caption}", bold=True, size=10, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
            para.paragraph_format.keep_with_next = True
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(header):
            c = t.rows[0].cells[i]; c.text = ""
            set_font(c.paragraphs[0].add_run(h), size=size, bold=True, color=RGBColor(255, 255, 255)); shade(c, "1E3A8A")
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                set_font(cells[i].paragraphs[0].add_run(str(v)), size=size)
                cells[i].paragraphs[0].paragraph_format.space_after = Pt(1)
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths): row.cells[i].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)
        return t

    def image(self, name, caption, width_cm=15.5):
        path = IMG / name
        if not path.exists():
            self.p(f"[image {name} missing]"); return
        para = self.doc.add_paragraph(); para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.keep_with_next = True
        para.add_run().add_picture(str(path), width=Cm(width_cm))
        self.fig += 1
        cp = self.p(f"Figure {self.fig}: {caption}", italic=True, size=9.5, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x47, 0x55, 0x69))

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def save(self, path):
        self.doc.save(path)


def ev(evidence: dict, sid: str):
    e = evidence[sid]
    return e["sql"], e["output"]


# ──────────────────────────── report ────────────────────────────
def build_report(d: dict, evidence: dict, ddl_text: str, defects: list[dict], dest: Path):
    R = Report()
    T = d["totals"]
    # Section 1 – title page
    for _ in range(3): R.p("", after=12)
    R.p("Database Systems Laboratory", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x64, 0x74, 0x8B))
    R.p("PROJECT REPORT", bold=True, size=14, align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0x64, 0x74, 0x8B)).runs[0].font.name = "Calibri"
    R.p(TITLE, bold=True, size=26, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
    R.p(SUB, italic=True, size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    R.p("", after=18)
    R.table(["Item", "Details"], [
        ["Project name", "MyGovt – AI-Powered Tamil Nadu Citizen Services Platform"],
        ["Student name(s)", PH_NAMES],
        ["Register number(s)", PH_REGS],
        ["Course code and name", COURSE],
        ["Faculty name", PH_FACULTY],
        ["Database management system", f"{d['version']} with PostGIS 3.6.2, pgvector 0.8.6, pg_trgm, pgcrypto, btree_gist"],
        ["Source code repository", "github.com/santhoshraja-15/My-Govt (branch audit/tn-data-verification)"],
    ], widths=[5, 11], size=10.5)
    R.p("Text in [square brackets] is a placeholder that the student must replace before submission.", italic=True, size=9.5,
        align=WD_ALIGN_PARAGRAPH.CENTER, color=RGBColor(0xB4, 0x53, 0x09))
    R.page_break()

    # contents (manual – avoids an out-of-date field)
    R.h("Contents", 1)
    for i, name in enumerate(["Project Title", "Introduction", "Objectives", "Software Requirements", "Database Design",
                              "Database Creation and Sample Data", "Database Operations and Outputs", "Advanced Database Features",
                              "Project Output Screenshots", "Conclusion", "References"], 1):
        R.p(f"{i}.  {name}", size=12, align=WD_ALIGN_PARAGRAPH.LEFT, after=3)
    R.page_break()

    R.h("1. Project Title", 1)
    R.p(f"{TITLE}. {SUB}.")
    R.table(["Item", "Details"], [["Student name(s)", PH_NAMES], ["Register number(s)", PH_REGS], ["Course", COURSE], ["Faculty", PH_FACULTY]], widths=[5, 11], size=10.5)

    R.h("2. Introduction", 1)
    R.p("Citizens of Tamil Nadu must discover government schemes, check whether they are eligible, find the documents a service needs, "
        "and, when something goes wrong, file a complaint and follow it to resolution. This information is spread over many department "
        "websites. MyGovt gathers it in one relational database and puts a web application, a rule-based eligibility checker, a "
        "grounded question-answering assistant and an officer console on top of it.")
    R.h("2.1 Problem statement", 2)
    R.p("Government information is fragmented, hard to verify and hard to act on. A citizen cannot easily tell which scheme applies to them, "
        "and a complaint filed with the wrong office is lost. The database must therefore (a) store schemes, services, departments and "
        "jurisdictions with a clear provenance, (b) route each complaint to the responsible authority, (c) keep a tamper-evident history of what "
        "happened to every complaint, and (d) never present unverified records as official fact.")
    R.h("2.2 Why a relational database", 2)
    R.bullets([
        ("Integrity: ", "primary keys, foreign keys, UNIQUE, NOT NULL and CHECK constraints reject invalid complaints, schemes and statuses at the database, not only in application code."),
        ("Relationships: ", "departments → authorities → officers → complaints; schemes ↔ eligibility rules ↔ documents are naturally relational."),
        ("Automatic behaviour: ", "triggers write complaint history and protect the audit log; views expose SLA breaches and department performance."),
        ("Spatial and semantic search: ", "PostGIS resolves a complaint location to a ward and local body; pgvector and full-text indexes support search – inside the same transactional database."),
    ])
    R.h("2.3 Scale of the implemented database", 2)
    R.table(["Measure", "Value"], [
        ["Schemas / tables", f"{len(d['schema_tables'])} schemas / {T['tables']} tables"],
        ["Columns", T["columns"]], ["Foreign keys", T["fks"]], ["Triggers", T["triggers"]],
        ["Project functions", "7 (PL/pgSQL)"], ["Views", "2 project views (+ 2 supplied by extensions)"],
        ["Index types in use", "B-tree, GIN, GiST (spatial), HNSW (vector)"],
    ], widths=[7, 9], caption="Size of the MyGovt database (counted from the catalog)")
    R.p("All government records in the prototype are marked 'provisional'; none has been confirmed against an official source document, and the "
        "database enforces this by a CHECK constraint (a record cannot be set to 'official_verified' without a source document reference). "
        "Complaint rows in the demonstration database include clearly labelled synthetic data.", italic=True, size=10)

    R.h("3. Objectives", 1)
    R.bullets([
        "Design a normalised relational schema for departments, jurisdictions, schemes, services, documents, citizens and complaints.",
        "Enforce data integrity with PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL and CHECK constraints.",
        "Automate complaint tracking with triggers, and protect the audit trail from modification.",
        "Provide views for SLA monitoring and department performance reporting.",
        "Demonstrate SELECT, INSERT, UPDATE, DELETE, joins, aggregates, subqueries, functions, procedures, views and transaction control (COMMIT, ROLLBACK, SAVEPOINT).",
        "Deliver a working web application (FastAPI + Next.js) that uses the database as its single system of record.",
    ])
    R.h("3.1 Scope", 2)
    R.p("In scope: the PostgreSQL database, its migrations, the REST API and the web interface for citizens, officers and administrators. "
        "Out of scope for this submission: confirming each record against official government sources (data is provisional), production hosting, "
        "and any integration with live government systems. Neo4j, Redis and MinIO are optional components and are not required by the database design.")

    R.h("4. Software Requirements", 1)
    R.table(["Component", "Technology / version"], [
        ["DBMS", f"{d['version']}"], ["Extensions", "PostGIS 3.6.2, pgvector 0.8.6, pg_trgm 1.6, pgcrypto 1.3, btree_gist 1.7"],
        ["Database tools", "psql, pgAdmin (optional); asyncpg driver"],
        ["Backend", "Python 3.12, FastAPI, SQLAlchemy (raw SQL via asyncpg), PyJWT, Argon2"],
        ["Frontend", "Next.js 15, React 18, Tailwind CSS, React Flow (ER diagram)"],
        ["Testing", "pytest, Playwright, axe-core"],
        ["Delivery", "Docker Compose, GitHub Actions (10 CI jobs)"],
        ["Operating system", "Windows 11 (development); Linux containers (CI)"],
        ["Optional", "Neo4j (graph), Redis (cache/rate limit), MinIO (object storage)"],
    ], widths=[4.5, 11.5], caption="Software requirements")

    # Section 5
    R.h("5. Database Design", 1)
    R.h("5.1 Entity–relationship diagram", 2)
    R.p("The ER diagram below is generated live from the PostgreSQL catalog by the application's Database Architecture Explorer, so it always "
        "matches the real database. Boxes are tables (coloured by schema), the key symbol marks a primary key, the link symbol a foreign key.")
    R.image("16_arch_er.png", "Entity–relationship diagram of all 50 tables (Database Architecture Explorer)", 15.5)
    R.image("17_arch_er_focus.png", "Focus view: the complaint table and its connected entities", 12)
    R.h("5.2 Core entities and relationships", 2)
    R.table(["Parent (one)", "Child (many)", "Foreign-key column(s)"], [[a, b, c] for b, a, c in d["fk_edges"]], widths=[5.5, 5.5, 5], size=9,
            caption="Foreign-key relationships among the core tables (each is 1 : N)")
    R.p("Cardinality: one department has many authorities, officers, schemes, services and complaints; one citizen files many complaints; one complaint has many "
        "history rows (written by a trigger); one scheme has many eligibility rules. Many-to-many relationships (for example schemes ↔ documents) are "
        "resolved by junction tables whose primary key is made of two foreign keys.")
    R.h("5.3 Tables, attributes, primary keys and foreign keys", 2)
    R.p("PK = primary key, FK = foreign key (target shown), UQ = unique, NN = NOT NULL. The twelve core tables used throughout this report are listed; the full 50-table catalog is in the repository.", size=10)
    for t in CORE:
        rows = []
        for a in d["attrs"][t]:
            keys = ", ".join(x for x in ["PK" if a["pk"] else "", f"FK → {a['fk']}" if a["fk"] else "", "UQ" if a["uq"] else ""] if x)
            rows.append([a["col"], a["type"], "NN" if a["nn"] else "", keys])
        shown = rows if len(rows) <= 16 else rows[:16] + [[f"… {len(rows) - 16} more columns", "", "", ""]]
        R.table(["Attribute", "Data type", "Null?", "Key"], shown, widths=[4.5, 4.5, 1.5, 5.5], size=8.5, caption=f"{t} ({len(rows)} columns)")
    R.h("5.4 Relational schema", 2)
    R.p("Notation: TABLE(PK: key, FK: foreign key, other attributes).")
    rel = []
    for t in ["administration.department", "administration.authority", "administration.officer", "identity.citizen", "schemes.scheme",
              "schemes.eligibility_rule", "services.service", "complaints.complaint_category", "complaints.complaint", "complaints.complaint_history"]:
        parts = []
        for a in d["attrs"][t][:9]:
            parts.append(f"PK:{a['col']}" if a["pk"] else (f"FK:{a['col']}" if a["fk"] else a["col"]))
        more = len(d["attrs"][t]) - 9
        rel.append(f"{t.split('.')[1].upper()}({', '.join(parts)}{f', … +{more} more' if more > 0 else ''})")
    R.code("\n".join(rel), size=8.5)
    R.h("5.5 Normalization", 2)
    R.p("The schema was designed so that every table describes one kind of thing and every non-key attribute depends on that thing's key.")
    R.bullets([
        ("First normal form (1NF): ", "every table has a primary key and atomic columns. The few jsonb / array columns (for example eligibility rule values and document lists) hold a single structured value that the application treats as a unit; they are not repeating groups of facts that are queried independently."),
        ("Second normal form (2NF): ", "all core tables use a single-column surrogate key (serial or UUID), so a non-key attribute cannot depend on part of a key. Junction tables use a composite key made only of foreign keys and carry no descriptive attributes."),
        ("Third normal form (3NF): ", "descriptive facts live once, in their own table – department names in administration.department, complaint category names and default SLA in complaints.complaint_category, jurisdiction names in the administration tables – and other tables reference them by foreign key instead of copying the text."),
    ])
    R.p("Honest limitation: functional dependencies are not recorded in the PostgreSQL catalog, so the Database Architecture Explorer reports structural facts "
        "(keys, atomic columns, possible duplicate columns) and does not claim that the whole schema is in 3NF. The statement above is the designer's analysis of the core tables, not a tool-verified proof.", italic=True, size=10)
    R.h("Deliberate denormalization", 3)
    R.p("complaints.complaint stores both department_id and authority_id even though the authority already determines its department. The values are the "
        "result of routing at the moment the complaint was filed; if the authority table is later reorganised, the complaint must keep the routing "
        "decision that was actually applied. This is a conscious trade-off of a small amount of redundancy for historical accuracy.")

    # Section 6
    R.h("6. Database Creation and Sample Data", 1)
    R.p(f"Database server: {d['version']}. The schema is created by database/schema/001_schema.sql followed by migrations 002–008. "
        "The statements below are copied from that file – they are the statements that built the database, not simplified examples.")
    R.h("6.1 CREATE TABLE statements", 2)
    R.p("Each table shows PRIMARY KEY, FOREIGN KEY (REFERENCES), UNIQUE, NOT NULL, DEFAULT and CHECK constraints.", size=10)
    for t in ["administration.department", "administration.authority", "administration.officer", "schemes.scheme", "schemes.eligibility_rule",
              "complaints.complaint_category", "complaints.complaint", "complaints.complaint_history", "identity.citizen"]:
        R.h(t, 3)
        R.code(ddl_for(ddl_text, t), size=7.5)
    R.h("6.2 Sample records (INSERT statements)", 2)
    R.p("The INSERT statements below were generated from rows that exist in the database (the verified seed in database/seed/002_verified_seed_data.sql "
        "and the demonstration data). Government records are provisional – the verification_status column says so for every row.", size=10)
    R.code("\n\n".join(d["inserts"]), size=8)
    R.h("6.3 Sample records as stored", 2)
    for sid in ["D1", "D2", "D3"]:
        sql, out = ev(evidence, sid)
        R.code(sql, size=8.5); R.output(out)
    R.p("Row counts of the core tables in the database used for this report:", size=10)
    R.table(["Table", "Rows"], [[t, d["counts"][t]] for t in CORE], widths=[9, 3], size=9.5, caption="Row counts (demonstration database including labelled synthetic complaints)")

    # Section 7
    R.h("7. Database Operations and Outputs", 1)
    R.p("All statements in this section were executed against a disposable copy of the demonstration database (mygovt_dev_report) by "
        "docs/submission/run_sql_evidence.py; the output shown is exactly what PostgreSQL returned. The same statements are in docs/submission/lab_queries.sql.", size=10)
    R.h("7.1 SELECT, JOIN, aggregates and subqueries", 2)
    for sid, label in [("Q5", "SELECT with ILIKE pattern and ORDER BY"), ("Q1", "INNER JOIN"), ("Q4", "LEFT JOIN with COUNT"), ("Q6", "Self-join"),
                       ("Q2", "Aggregate functions with GROUP BY"), ("Q3", "Subquery (nested aggregate)")]:
        R.h(f"{label}", 3)
        sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("7.2 INSERT, UPDATE and DELETE", 2)
    for sid, label in [("M1", "INSERT"), ("M2", "UPDATE"), ("M3", "Verify the change"), ("M4", "DELETE"), ("M5", "Verify the deletion")]:
        R.h(label, 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("7.3 Constraint enforcement (statements that the database rejects)", 2)
    R.p("Each of the following statements is deliberately invalid. The error text is PostgreSQL's own.", size=10)
    for sid in ["C1", "C2", "C3", "C4", "C5"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("7.4 Transaction control: COMMIT, ROLLBACK, SAVEPOINT", 2)
    for sid in ["X1", "X2", "X3", "X4", "X5", "X6", "X7"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.p("Result: after ROLLBACK the priority was unchanged; after ROLLBACK TO SAVEPOINT and COMMIT only the first update ('high') persisted, the second ('low') was undone.", size=10)

    # Section 8
    R.h("8. Advanced Database Features", 1)
    R.h("8.1 Functions", 2)
    R.p("The project defines seven PL/pgSQL functions. Five are trigger functions; resolve_jurisdiction is a callable table function.")
    sql, out = ev(evidence, "F1"); R.code(sql); R.output(out)
    for fn in ["administration.resolve_jurisdiction", "complaints.log_status_change"]:
        body = func_def(ddl_text, fn)
        if body:
            R.h(fn, 3); R.code(body, size=7.5)
    R.h("Calling a function", 3)
    sql, out = ev(evidence, "F2"); R.code(sql); R.output(out)
    R.p("The function returns NULLs here because jurisdiction boundary polygons (ward, taluk, district geometries) are not loaded in the demonstration "
        "database; with boundary data it returns the ward, local body, taluk and district that contain the point.", italic=True, size=10)
    R.h("8.2 Stored procedure", 2)
    R.p("PostgreSQL supports stored procedures (CREATE PROCEDURE … CALL) that, unlike functions, can control transactions. The MyGovt application itself uses "
        "functions and triggers and has no stored procedure. To satisfy the lab requirement, the procedure below was written for this report and created "
        "ONLY on the scratch database; it is illustrative and is not part of the application.", size=10)
    for sid in ["P1", "P2", "P3", "P4"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("8.3 Triggers", 2)
    R.p("Thirteen triggers exist. The three below are the most important: complaint history, append-only audit log, and the verification-status log.")
    body = func_def(ddl_text, "complaints.log_status_change")
    if body: R.code(body + NL2 + (trigger_def(ddl_text, "trg_complaint_history") or ""), size=7.5)
    for sid in ["T1", "T2", "T3", "T4", "T5", "T6"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("8.4 Views", 2)
    for sid in ["V1", "V2", "V3"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)
    R.h("8.5 Indexes and extensions", 2)
    for sid in ["I1", "I2", "I3"]:
        R.h(evidence[sid]["title"], 3); sql, out = ev(evidence, sid); R.code(sql); R.output(out)

    # Section 9
    R.h("9. Project Output Screenshots", 1)
    R.p("Screenshots were captured from the running application (Next.js front end, FastAPI back end, PostgreSQL database) by an automated script, "
        "docs/submission/../../frontend/audit/submission_shots.js; they show real data from the demonstration database.", size=10)
    R.h("9.1 Database structure and sample records", 2)
    R.image("18_arch_schema.png", "Relational schema browser (tables, keys, notation, example joins)", 15)
    R.image("19_arch_implementation.png", "Implementation browser (actual CREATE TABLE text, constraints, indexes, row counts)", 15)
    R.image("20_arch_advanced.png", "Advanced concepts: triggers, functions, views and transactions found in the database", 15)
    R.image("14_admin_schema_explorer.png", "Administrator schema explorer", 15)
    R.h("9.2 Query execution", 2)
    R.p("Query execution is shown as text with outputs in Sections 7 and 8; the administrator SQL workspace in the application runs read-only queries as follows.")
    R.image("12_admin_overview.png", "Administrator overview", 15)
    R.image("13_admin_verification.png", "Verification queue: records awaiting verification against an official source", 15)
    R.h("9.3 Application screens", 2)
    for f, cap in [("01_landing.png", "Landing page"), ("02_schemes.png", "Scheme search and filters"), ("03_eligibility.png", "Eligibility checker (rule-based)"),
                   ("04_services.png", "Service search"), ("05_documents.png", "Document requirements"), ("06_citizen_dashboard.png", "Citizen dashboard"),
                   ("07_file_complaint.png", "Complaint filing form"), ("08_my_complaints.png", "Complaint list and tracking"),
                   ("09_assistant.png", "AI assistant (grounded in the database)"), ("10_officer_console.png", "Officer console (department-scoped queue)"),
                   ("11_officer_detail.png", "Officer complaint detail with history and status actions"), ("15_arch_architecture.png", "Architecture overview")]:
        R.image(f, cap, 15)

    R.h("10. Conclusion", 1)
    R.p("MyGovt demonstrates a complete database-backed application: a normalised PostgreSQL schema of 50 tables with enforced keys and constraints; "
        "triggers that record the history of every complaint and make the audit log append-only; views that report SLA breaches and department performance; "
        "spatial and vector indexes for location and search; and a web application whose every figure is read from the database.")
    R.h("10.1 Testing and results", 2)
    fixed = sum(1 for x in defects if x["status"].upper().startswith("FIXED"))
    R.table(["Check", "Result"], [
        ["Automated tests (pytest + Playwright)", "525 backend tests collected (133 unit tests); 103 end-to-end browser tests"],
        ["Hosted continuous integration", "GitHub Actions run 39298767536 on commit 586d690: 10 of 10 jobs passed (backend, frontend, e2e, security, SQL and data checks, 4 image builds, Compose stack)"],
        ["System audit", "15/15 routes, 530 controls clicked, 67 API operations probed (0 access-control anomalies), 56 data-consistency checks (0 mismatches)"],
        ["Defects found and fixed", f"{len(defects)} recorded in docs/audit/defect_register.csv: {fixed} fixed (each with a regression test or probe), {len(defects) - fixed} left open as documented limitations"],
        ["SQL evidence", f"{len(evidence)} statements executed for this report; the only errors are the deliberate constraint-violation demonstrations"],
    ], widths=[5.5, 10.5], caption="Testing summary (details: docs/complete_system_audit.md)")
    R.h("10.2 Limitations", 2)
    R.bullets([
        "No government record is officially verified: all schemes, services and departments are 'provisional' pending confirmation against official documents.",
        "Third normal form is argued from the design but is not verified by a tool (functional dependencies are not stored in the catalog).",
        "The application has no SQL stored procedure; the procedure in Section 8.2 is illustrative.",
        "Jurisdiction boundary polygons are not loaded, so spatial routing by coordinates is demonstrated structurally only.",
        "The system is ready for a university demonstration, not for public release (see docs/complete_system_audit.md §14).",
    ])
    R.h("10.3 Future enhancements", 2)
    R.bullets(["Verify records against official documents and move them to 'official_verified' through the governed workflow.",
               "Load ward / taluk / district boundaries to enable automatic location-based routing.",
               "Table partitioning for the audit log and complaint history as volume grows.",
               "Notification (SMS / e-mail) on status changes; mobile application; full Tamil content review."])

    R.h("11. References", 1)
    R.bullets([
        "PostgreSQL 16 Documentation – https://www.postgresql.org/docs/16/",
        "PostGIS 3 Documentation – https://postgis.net/documentation/",
        "pgvector – https://github.com/pgvector/pgvector",
        "Silberschatz, A., Korth, H. F., Sudarshan, S. Database System Concepts, McGraw-Hill.",
        "Elmasri, R., Navathe, S. B. Fundamentals of Database Systems, Pearson.",
        "FastAPI – https://fastapi.tiangolo.com/ ;  Next.js – https://nextjs.org/docs",
        "Government of Tamil Nadu – official department websites (source of the provisional scheme and service records).",
        "Project repository – https://github.com/santhoshraja-15/My-Govt (docs/complete_system_audit.md, docs/database-architecture.md).",
    ], style="List Number")
    R.save(dest)


def ddl_all(t: str) -> str:
    return t


def func_def(ddl_text: str, name: str) -> str | None:
    """Last (i.e. latest migration) definition of a function, up to its LANGUAGE clause."""
    ms = list(re.finditer(rf"CREATE (?:OR REPLACE )?FUNCTION {re.escape(name)}\(.*?\$\$\s*LANGUAGE\s+\w+[^;]*;", ddl_text, re.S))
    return ms[-1].group(0) if ms else None


def trigger_def(ddl_text: str, name: str) -> str | None:
    m = re.search(rf"CREATE TRIGGER {re.escape(name)}.*?;", ddl_text, re.S)
    return m.group(0) if m else None


# ──────────────────────────── pptx ────────────────────────────
BG = PRGB(0xFF, 0xFF, 0xFF); INK = PRGB(0x0F, 0x17, 0x2A); BLUE = PRGB(0x1E, 0x3A, 0x8A); GREY = PRGB(0x64, 0x74, 0x8B); AMBER = PRGB(0xB4, 0x53, 0x09)


class Deck:
    def __init__(self):
        self.p = Presentation()
        self.p.slide_width, self.p.slide_height = Inches(13.333), Inches(7.5)
        self.n = 0

    def _slide(self, title):
        s = self.p.slides.add_slide(self.p.slide_layouts[6]); self.n += 1
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, self.p.slide_width, Inches(1.0)); bar.fill.solid(); bar.fill.fore_color.rgb = BLUE; bar.line.fill.background()
        tb = s.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(12.3), Inches(0.7)); tf = tb.text_frame; tf.word_wrap = True
        r = tf.paragraphs[0].add_run(); r.text = title; r.font.size = PPt(30); r.font.bold = True; r.font.color.rgb = PRGB(255, 255, 255); r.font.name = "Calibri"
        ft = s.shapes.add_textbox(Inches(0.5), Inches(7.05), Inches(12.3), Inches(0.35)); fr = ft.text_frame.paragraphs[0].add_run()
        fr.text = f"MyGovt · BCSE302P Database Systems Lab · {self.n}"; fr.font.size = PPt(11); fr.font.color.rgb = GREY; fr.font.name = "Calibri"
        return s

    def _text(self, s, x, y, w, h, lines, size=20, mono=False, color=INK, bold_first=False):
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
        for i, ln in enumerate(lines):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r = para.add_run(); r.text = ln; r.font.size = PPt(size); r.font.color.rgb = color
            r.font.name = "Consolas" if mono else "Calibri"
            if bold_first and i == 0: r.font.bold = True
            para.space_after = PPt(6 if not mono else 0)
        return tb

    def title(self, title, sub, lines):
        s = self.p.slides.add_slide(self.p.slide_layouts[6]); self.n += 1
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, self.p.slide_width, self.p.slide_height); bg.fill.solid(); bg.fill.fore_color.rgb = BLUE; bg.line.fill.background()
        self._text(s, 0.8, 1.2, 11.7, 1.6, [title], 40, color=PRGB(255, 255, 255), bold_first=True)
        self._text(s, 0.8, 2.9, 11.7, 1.0, [sub], 20, color=PRGB(0xBF, 0xDB, 0xFE))
        self._text(s, 0.8, 4.3, 11.7, 2.4, lines, 20, color=PRGB(255, 255, 255))

    def bullets(self, title, items, size=22, note=None):
        s = self._slide(title)
        self._text(s, 0.7, 1.4, 12, 5.2, ["•  " + i for i in items], size)
        if note: self._text(s, 0.7, 6.5, 12, 0.5, [note], 13, color=AMBER)

    @staticmethod
    def _fit(text, width_in, height_in, size):
        """Wrap to the box width and truncate to its height so nothing runs off the slide."""
        import textwrap
        cpl = max(20, int(width_in * 72 / (size * 0.56)))
        maxl = max(4, int(height_in * 72 / (size * 1.25)))
        lines = []
        for ln in text.split("\n"):
            lines += textwrap.wrap(ln, cpl, subsequent_indent="    ", break_long_words=True, replace_whitespace=False, drop_whitespace=False) or [""]
        if len(lines) > maxl:
            lines = lines[: maxl - 1] + ["... (continues in the Word report)"]
        return lines

    def code(self, title, code, out=None, size=13, split=False, note=None):
        s = self._slide(title)
        if out is None:
            self._text(s, 0.6, 1.25, 12.1, 5.3, self._fit(code, 12.0, 5.3, size), size, mono=True)
        else:
            self._text(s, 0.5, 1.2, 6.1, 5.4, self._fit(code, 6.0, 5.4, size), size, mono=True)
            osz = max(size - 1, 9)
            self._text(s, 6.75, 1.2, 6.2, 5.4, self._fit(out, 6.1, 5.4, osz), osz, mono=True, color=PRGB(0x06, 0x4E, 0x3B))
        if note: self._text(s, 0.6, 6.6, 12, 0.4, [note], 12, color=AMBER)

    def image(self, title, name, caption=None):
        s = self._slide(title)
        path = IMG / name
        if path.exists():
            from PIL import Image
            w, h = Image.open(path).size
            maxw, maxh = Inches(12.3), Inches(5.55) if caption else Inches(5.75)
            sc = min(maxw / w, maxh / h)
            pw, ph = int(w * sc), int(h * sc)
            s.shapes.add_picture(str(path), int((self.p.slide_width - pw) / 2), Inches(1.15), pw, ph)
        if caption: self._text(s, 0.6, 6.7, 12, 0.35, [caption], 13, color=GREY)

    def table(self, title, header, rows, size=14, widths=None):
        s = self._slide(title)
        tbl = s.shapes.add_table(len(rows) + 1, len(header), Inches(0.6), Inches(1.3), Inches(12.1), Inches(0.4 * (len(rows) + 1))).table
        for i, h in enumerate(header):
            c = tbl.cell(0, i); c.text = h
            for para in c.text_frame.paragraphs:
                for r in para.runs: r.font.size = PPt(size); r.font.bold = True
        for ri, row in enumerate(rows, 1):
            for ci, v in enumerate(row):
                c = tbl.cell(ri, ci); c.text = str(v)
                for para in c.text_frame.paragraphs:
                    for r in para.runs: r.font.size = PPt(size)
        if widths:
            for i, w in enumerate(widths): tbl.columns[i].width = Inches(w)

    def save(self, path): self.p.save(path)


def short(sid, evidence, maxlines=14):
    e = evidence[sid]
    return e["sql"], "\n".join(e["output"].split("\n")[:maxlines])


def build_deck(d: dict, evidence: dict, ddl_text: str, dest: Path):
    D = Deck(); T = d["totals"]
    D.title(TITLE, SUB, ["Student(s): " + PH_NAMES, "Register no.: " + PH_REGS, COURSE, "Faculty: " + PH_FACULTY,
                         "(bracketed text = placeholders to fill)"])
    D.bullets("Abstract and Problem Statement", [
        "Tamil Nadu citizens face scattered scheme, service and complaint information on many department websites.",
        "MyGovt keeps it in one PostgreSQL database and adds a web app, eligibility checker, grounded assistant and officer console.",
        "Complaints are routed to the responsible authority; every status change is recorded by a database trigger.",
        "Government records are 'provisional' – the schema forbids marking them verified without a source document."], 22)
    D.bullets("Objectives and Scope", [
        "Normalised schema: departments, jurisdictions, schemes, services, citizens, complaints",
        "Integrity via PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK",
        "Automation: triggers (complaint history, append-only audit), views (SLA, performance)",
        "Demonstrate SELECT / INSERT / UPDATE / DELETE, joins, aggregates, subqueries, transactions",
        "Scope: database + API + web UI.  Not in scope: verifying records against official sources, production hosting"], 21)
    D.image("System Architecture", "15_arch_architecture.png", "Generated by the Database Architecture Explorer from the running system")
    D.bullets("Workflow", [
        "Citizen files a complaint  →  API validates (CHECK / FK constraints)",
        "Routing: category + jurisdiction → department and authority (frozen on the row)",
        "INSERT / UPDATE of status  →  trigger writes complaints.complaint_history",
        "Officer (department-scoped) assigns / progresses the complaint; allowed transitions enforced by a state machine",
        "Views report SLA breaches and department performance; audit log is append-only"], 21)
    D.image("ER Diagram – 50 tables, 10 schemas", "16_arch_er.png")
    D.image("ER Diagram – Complaint focus", "17_arch_er_focus.png")
    rows = [[t, d["counts"][t]] for t in CORE[:0]]
    D.bullets("Relational Schema", [
        "DEPARTMENT(PK:department_id, department_code UQ, department_name, status, verification_status)",
        "AUTHORITY(PK:authority_id, FK:department_id, authority_name, parent_authority_id …)",
        "SCHEME(PK:scheme_id, scheme_code UQ, scheme_name, scheme_level, FK:department_id, status …)",
        "ELIGIBILITY_RULE(PK:rule_id, FK:scheme_id, rule_type, operator, value …)",
        "COMPLAINT(PK:complaint_id, complaint_ref UQ, FK:citizen_id, FK:category_id, FK:department_id, FK:authority_id, status, priority …)",
        "COMPLAINT_HISTORY(PK:history_id, FK:complaint_id, old_status, new_status, changed_at …)"], 17)
    D.bullets("Normalization", [
        "1NF: primary key + atomic columns on every core table",
        "2NF: single-column surrogate keys; junction tables hold only foreign keys",
        "3NF: names and SLAs stored once (department, category) and referenced by FK",
        "Deliberate denormalization: complaint stores department_id AND authority_id (routing result frozen for history)",
        "Honest note: 3NF is the designer's analysis – the catalog cannot prove functional dependencies"], 20)
    D.bullets("Database Implementation – DBMS", [
        f"{d['version']}  +  PostGIS 3.6.2, pgvector 0.8.6, pg_trgm, pgcrypto, btree_gist",
        f"{len(d['schema_tables'])} schemas · {T['tables']} tables · {T['columns']} columns · {T['fks']} foreign keys · {T['triggers']} triggers",
        "Indexes: B-tree, GIN (full text), GiST (spatial), HNSW (vector)",
        "Created by 001_schema.sql + migrations 002–008; seed 002_verified_seed_data.sql"], 22)
    for t, size in [("administration.department", 12), ("schemes.scheme", 10), ("complaints.complaint", 8)]:
        txt = ddl_for(ddl_text, t); lines = txt.split("\n")
        D.code(f"CREATE TABLE – {t}", "\n".join(lines[:34]), size=size, note="Full statements: Word report §6.1" if len(lines) > 34 else None)
    D.code("CREATE TABLE – complaints.complaint_history", ddl_for(ddl_text, "complaints.complaint_history"), size=13)
    D.code("Sample records – INSERT statements", "\n".join(d["inserts"][:6]).replace("\n\n", "\n"), size=11)
    for sid in ["Q1", "Q2", "Q3"]:
        sql, out = short(sid, evidence)
        D.code(f"SQL query – {evidence[sid]['title']}", sql, out, size=11)
    for sid in ["M1", "M2", "M4"]:
        sql, out = short(sid, evidence); D.code(f"DML – {evidence[sid]['title']}", sql, out, size=12)
    sql, out = short("C1", evidence); D.code("Constraint: UNIQUE", sql, out, size=12)
    sql, out = short("C3", evidence); D.code("Constraint: FOREIGN KEY", sql, out, size=12)
    sql, out = short("C2", evidence); D.code("Constraint: CHECK", sql, out, size=12)
    D.bullets("Advanced Concepts – overview", [
        "Functions (7, PL/pgSQL): resolve_jurisdiction, log_status_change, refresh_tsv, touch_updated_at, block_mutation, fill_location, log_verification_change",
        "Triggers (13): complaint history, append-only audit log, updated_at, search vectors, verification log",
        "Views: v_sla_breached, v_department_performance",
        "Procedure: PostgreSQL CALL demonstrated with an illustrative procedure (scratch DB only – the app itself has none)",
        "Transactions: BEGIN / COMMIT / ROLLBACK / SAVEPOINT"], 20)
    body = func_def(ddl_text, "complaints.log_status_change")
    if body: D.code("Trigger – complaint history", body + NL2 + (trigger_def(ddl_text, "trg_complaint_history") or ""), size=11)
    D.code("Trigger in action", evidence["T2"]["sql"], evidence["T3"]["output"], size=11, note="UPDATE of status fired the trigger → new row in complaint_history")
    sql, out = short("T5", evidence); D.code("Trigger – append-only audit log", sql, out, size=13)
    sql, out = short("V1", evidence); D.code("View – v_department_performance", sql, out, size=13)
    sql, out = short("P1", evidence); D.code("Stored procedure (illustrative) – CREATE", sql, None, size=13, note="Created on the scratch database only; not part of the application")
    sql, out = short("P3", evidence); D.code("Stored procedure – CALL", sql + "\n\n-- before:\n" + evidence["P2"]["output"] + "\n-- after:\n" + evidence["P4"]["output"], out, size=11)
    tx = "\n".join(f"-- {evidence[s]['title']}\n{evidence[s]['sql']}\n" for s in ["X1", "X2", "X3"])
    D.code("Transactions – ROLLBACK", tx, evidence["X4"]["output"], size=11, note="After ROLLBACK the priority is unchanged (medium)")
    tx = "\n".join(f"-- {evidence[s]['title']}\n{evidence[s]['sql']}" for s in ["X5", "X6"])
    D.code("Transactions – SAVEPOINT and COMMIT", tx, evidence["X7"]["output"], size=10, note="Only the first update persisted")
    for f, t in [("01_landing.png", "Application – Landing"), ("02_schemes.png", "Application – Scheme search"), ("03_eligibility.png", "Application – Eligibility checker"),
                 ("07_file_complaint.png", "Application – File a complaint"), ("11_officer_detail.png", "Application – Officer complaint detail"),
                 ("12_admin_overview.png", "Application – Administrator overview"), ("19_arch_implementation.png", "Database structure – Implementation browser")]:
        D.image(t, f)
    fixed = "see defect register"
    D.table("Testing and Results", ["Check", "Result"], [
        ["Backend tests", "525 collected (133 unit)"], ["Browser end-to-end", "103 Playwright tests"],
        ["Hosted CI (run 39298767536)", "10 / 10 jobs passed"], ["System audit", "15 routes · 530 controls · 67 API ops · 56 consistency checks"],
        ["SQL evidence", f"{len(evidence)} statements executed; only deliberate violations error"]], 16, [4.5, 7.6])
    D.bullets("Conclusion and Future Enhancement", [
        "A working database-backed platform: 50 tables, enforced integrity, triggers, views, spatial and vector search",
        "Limits: records provisional (0 officially verified); 3NF argued not proven; no stored procedure in app; boundaries not loaded",
        "Future: verify records with official documents · load jurisdiction boundaries · partition audit/history · notifications · mobile app"], 21)
    D.bullets("References", [
        "PostgreSQL 16 documentation – postgresql.org/docs/16", "PostGIS documentation – postgis.net", "pgvector – github.com/pgvector/pgvector",
        "Silberschatz, Korth, Sudarshan – Database System Concepts", "Elmasri, Navathe – Fundamentals of Database Systems",
        "Project repository – github.com/santhoshraja-15/My-Govt"], 22)
    D.save(dest)


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--dsn", required=True); a = ap.parse_args()
    d = await gather(a.dsn)
    evidence = {e["id"]: e for e in json.loads((HERE / "sql_evidence.json").read_text(encoding="utf-8"))}
    ddl_text = "\n".join((ROOT / "database" / "schema" / f).read_text(encoding="utf-8") for f in ["001_schema.sql"])
    extra = []
    for f in sorted((ROOT / "database" / "migrations").glob("*.sql")) if (ROOT / "database" / "migrations").exists() else []:
        extra.append(f.read_text(encoding="utf-8"))
    ddl_text += "\n" + "\n".join(extra)
    with open(ROOT / "docs" / "audit" / "defect_register.csv", encoding="utf-8", newline="") as fh:
        defects = list(csv.DictReader(fh))
    build_report(d, evidence, ddl_text, defects, HERE / "MyGovt_Project_Report.docx")
    build_deck(d, evidence, ddl_text, HERE / "MyGovt_Final_PPT.pptx")
    print("built", d["totals"], "inserts:", len(d["inserts"]), "defects:", len(defects))


if __name__ == "__main__":
    asyncio.run(main())
