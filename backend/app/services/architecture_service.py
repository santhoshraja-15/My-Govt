"""Read-only introspection of the REAL database for the Database Architecture Explorer.

Everything is derived from the PostgreSQL system catalogs and from the backend source tree at request time; nothing about the
schema is duplicated in the frontend. Only metadata is read. Row data is exposed solely as small samples of an allow-listed
set of catalogue tables, with sensitive-looking and bulky columns removed. Example queries are fixed (never user supplied) and
run inside a read-only transaction with a statement timeout.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.health import get_health_status

BACKEND_DIR = Path(__file__).resolve().parents[2]
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast", "public")

DOMAINS: dict[str, tuple[str, str]] = {
    "identity": ("Identity & consent", "#2563eb"),
    "administration": ("Administration & jurisdictions", "#0f766e"),
    "schemes": ("Schemes & eligibility", "#c2410c"),
    "services": ("Services", "#7c3aed"),
    "complaints": ("Complaints & routing", "#dc2626"),
    "documents": ("Documents & retrieval", "#0369a1"),
    "policies": ("Policies & orders", "#a16207"),
    "ai": ("AI assistant", "#be185d"),
    "audit": ("Audit trail", "#475569"),
    "system": ("Provenance & ingestion", "#4d7c0f"),
}

# Tables whose rows are public catalogue data (never personal data); only these may show a sample.
SAMPLE_ALLOWED = {
    "schemes.scheme", "services.service", "administration.department", "administration.district",
    "administration.authority", "complaints.complaint_category", "complaints.routing_rule",
    "schemes.eligibility_rule", "system.feature_flag",
}
SENSITIVE_COLUMN = re.compile(r"password|token|secret|hash|email|phone|address|aadhaar|ip_address|contact", re.I)
BULKY_TYPES = ("vector", "tsvector", "geometry", "geography", "bytea")
GENERIC_COLUMNS = {
    "status", "description", "notes", "created_at", "updated_at", "name", "is_active", "metadata", "language", "version",
    "verification_status", "source_document_ref", "verified_at", "verified_by", "name_ta", "title", "category", "priority",
    "effective_from", "effective_to", "source_url", "official_url", "website_url", "jurisdiction_level", "jurisdiction_id",
}


def q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


# ───────────────────────────────────────── catalog loading ─────────────────────────────────────────
async def load_catalog(db: AsyncSession) -> dict[str, Any]:
    schemas = [r[0] for r in (await db.execute(text(
        "SELECT nspname FROM pg_namespace WHERE nspname <> ALL(:sys) AND nspname !~ '^pg_' ORDER BY 1"), {"sys": list(SYSTEM_SCHEMAS)})).fetchall()]
    tables_rows = (await db.execute(text("""
        SELECT n.nspname, c.relname, obj_description(c.oid, 'pg_class') AS comment, c.relkind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r','p') AND n.nspname = ANY(:s)
          AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
        ORDER BY 1, 2"""), {"s": schemas})).fetchall()
    cols = (await db.execute(text("""
        SELECT n.nspname, c.relname, a.attname, format_type(a.atttypid, a.atttypmod) AS data_type, a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid) AS col_default, a.attnum
        FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attnum > 0 AND NOT a.attisdropped AND c.relkind IN ('r','p') AND n.nspname = ANY(:s)
        ORDER BY n.nspname, c.relname, a.attnum"""), {"s": schemas})).fetchall()
    cons = (await db.execute(text("""
        SELECT n.nspname, c.relname, con.conname, con.contype::text,
               pg_get_constraintdef(con.oid) AS definition,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum) AS cols,
               refn.nspname, refc.relname,
               (SELECT array_agg(a.attname::text ORDER BY k.ord) FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum) AS ref_cols,
               con.confdeltype::text, con.confupdtype::text
        FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_class refc ON refc.oid = con.confrelid LEFT JOIN pg_namespace refn ON refn.oid = refc.relnamespace
        WHERE con.contype IN ('p','u','f','c') AND n.nspname = ANY(:s)
        ORDER BY n.nspname, c.relname, con.contype, con.conname"""), {"s": schemas})).fetchall()
    idx = (await db.execute(text("""
        SELECT n.nspname, t.relname, i.relname, am.amname, ix.indisunique, ix.indisprimary, pg_get_indexdef(ix.indexrelid)
        FROM pg_index ix JOIN pg_class i ON i.oid = ix.indexrelid JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace JOIN pg_am am ON am.oid = i.relam
        WHERE n.nspname = ANY(:s) AND t.relkind IN ('r','p') ORDER BY 1, 2, 3"""), {"s": schemas})).fetchall()

    tables: dict[str, dict[str, Any]] = {}
    for schema, name, comment, kind in tables_rows:
        key = f"{schema}.{name}"
        domain = DOMAINS.get(schema, (schema.title(), "#64748b"))
        tables[key] = {"key": key, "schema": schema, "name": name, "comment": comment, "partitioned": kind == "p",
                       "domain": domain[0], "color": domain[1], "columns": [], "primary_key": [], "unique": [], "checks": [],
                       "foreign_keys": [], "indexes": [], "referenced_by": [], "row_count": None}
    for schema, name, col, dtype, notnull, default, _num in cols:
        t = tables.get(f"{schema}.{name}")
        if t is not None:
            t["columns"].append({"name": col, "type": dtype, "not_null": bool(notnull), "default": default})
    fks: list[dict[str, Any]] = []
    for schema, name, cname, ctype, definition, ccols, rschema, rtable, rcols, deltype, updtype in cons:
        t = tables.get(f"{schema}.{name}")
        if t is None:
            continue
        ccols = list(ccols or [])
        if ctype == "p":
            t["primary_key"] = ccols
        elif ctype == "u":
            t["unique"].append({"name": cname, "columns": ccols})
        elif ctype == "c":
            t["checks"].append({"name": cname, "definition": definition})
        elif ctype == "f":
            fk = {"name": cname, "from_table": t["key"], "from_columns": ccols, "to_table": f"{rschema}.{rtable}",
                  "to_columns": list(rcols or []), "on_delete": _ACTIONS.get(deltype, deltype), "on_update": _ACTIONS.get(updtype, updtype),
                  "enforced": True, "kind": "foreign_key"}
            t["foreign_keys"].append(fk)
            fks.append(fk)
    for schema, name, iname, method, unique, primary, definition in idx:
        t = tables.get(f"{schema}.{name}")
        if t is not None:
            t["indexes"].append({"name": iname, "method": method, "unique": bool(unique), "primary": bool(primary), "definition": definition})
    for fk in fks:
        target = tables.get(fk["to_table"])
        if target is not None:
            target["referenced_by"].append({"table": fk["from_table"], "columns": fk["from_columns"], "constraint": fk["name"]})
    for t in tables.values():
        t["column_names"] = [c["name"] for c in t["columns"]]
    for fk in fks:
        _annotate_cardinality(tables, fk)
    return {"schemas": schemas, "tables": tables, "foreign_keys": fks}


_ACTIONS = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def _index_columns(definition: str) -> list[str] | None:
    """Plain column list of an index definition, or None when it uses expressions."""
    m = re.search(r"USING \w+ \(([^()]*)\)", definition)
    if not m:
        return None
    cols = [c.strip().strip('"') for c in m.group(1).split(",")]
    return cols if all(re.fullmatch(r"\w+", c) for c in cols) else None


def _annotate_cardinality(tables: dict[str, dict[str, Any]], fk: dict[str, Any]) -> None:
    """one_to_one when the referencing columns are themselves unique (PK/UNIQUE/unique index); otherwise one_to_many."""
    child = tables[fk["from_table"]]
    cols = set(fk["from_columns"])
    unique_sets = [set(child["primary_key"])] + [set(u["columns"]) for u in child["unique"]]
    for i in child["indexes"]:
        if i["unique"] and (ic := _index_columns(i["definition"])):
            unique_sets.append(set(ic))
    by_name = {c["name"]: c for c in child["columns"]}
    nullable = any(not by_name[col]["not_null"] for col in fk["from_columns"])
    fk["cardinality"] = "one_to_one" if cols in unique_sets else "one_to_many"
    fk["child_participation"] = "optional" if nullable else "mandatory"
    fk["notation"] = ("1 : 0..1" if nullable else "1 : 1") if fk["cardinality"] == "one_to_one" else ("1 : 0..N" if nullable else "1 : 1..N")


def junction_relationships(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Many-to-many links through junction tables: the PRIMARY KEY consists only of foreign-key columns (>= 2 foreign keys)."""
    out = []
    for t in catalog["tables"].values():
        pk = set(t["primary_key"])
        fk_cols = {c for fk in t["foreign_keys"] for c in fk["from_columns"]}
        if len(t["foreign_keys"]) >= 2 and pk and pk <= fk_cols:
            targets = [fk["to_table"] for fk in t["foreign_keys"]]
            for i, a in enumerate(targets):
                for b in targets[i + 1:]:
                    if a != b:
                        out.append({"name": f"{t['key']} (junction)", "from_table": a, "to_table": b, "via": t["key"],
                                    "cardinality": "many_to_many", "notation": "N : M", "enforced": True, "kind": "junction"})
    return out


def inferred_relationships(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Columns that look like references (name matches another table's single-column key) but have NO foreign key."""
    pk_index: dict[str, list[str]] = defaultdict(list)
    for t in catalog["tables"].values():
        if len(t["primary_key"]) == 1:
            pk_index[t["primary_key"][0]].append(t["key"])
    out = []
    for t in catalog["tables"].values():
        fk_cols = {c for fk in t["foreign_keys"] for c in fk["from_columns"]}
        for col in t["columns"]:
            n = col["name"]
            if n in fk_cols or n in t["primary_key"] or not n.endswith("_id"):
                continue
            targets = [k for k in pk_index.get(n, []) if k != t["key"]]
            if len(targets) == 1:
                out.append({"name": f"{t['key']}.{n} ~ {targets[0]}", "from_table": t["key"], "from_columns": [n], "to_table": targets[0],
                            "to_columns": [n], "enforced": False, "kind": "inferred", "cardinality": "one_to_many (inferred)",
                            "notation": "inferred from the column name; not enforced by the database"})
    return out


# ───────────────────────────────────────── source scan (real usage) ─────────────────────────────────────────
_SOURCE_CACHE: dict[str, list[str]] | None = None


def source_usage(table_keys: list[str]) -> dict[str, list[str]]:
    """Which backend source files mention `schema.table` (static scan of app/, scripts/, etl/, knowledge_graph/)."""
    global _SOURCE_CACHE
    if _SOURCE_CACHE is None:
        texts: dict[str, str] = {}
        for folder in ("app", "scripts", "etl", "knowledge_graph", "ai"):
            for path in (BACKEND_DIR / folder).rglob("*.py"):
                if "__pycache__" in path.parts or path.name == "architecture_service.py":
                    continue
                try:
                    texts[path.relative_to(BACKEND_DIR).as_posix()] = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
        _SOURCE_CACHE = {}
        for key in table_keys:
            pat = re.compile(r"(?<![\w.])" + re.escape(key) + r"(?![\w])")
            _SOURCE_CACHE[key] = sorted(f for f, body in texts.items() if pat.search(body))
    return {k: _SOURCE_CACHE.get(k, []) for k in table_keys}


def database_files() -> dict[str, list[dict[str, Any]]]:
    root = next((p for p in (BACKEND_DIR.parent / "database", Path("/database")) if p.is_dir()), None)
    out: dict[str, list[dict[str, Any]]] = {"schema": [], "migrations": [], "seeds": []}
    if root is None:
        return out
    for group, folder in (("schema", "schema"), ("migrations", "migrations"), ("seeds", "seeds")):
        d = root / folder
        if d.is_dir():
            out[group] = [{"file": f"database/{folder}/{p.name}", "bytes": p.stat().st_size} for p in sorted(d.glob("*.sql"))]
    return out


# ───────────────────────────────────────── views over the catalog ─────────────────────────────────────────
def table_summary(t: dict[str, Any]) -> dict[str, Any]:
    return {"key": t["key"], "schema": t["schema"], "name": t["name"], "domain": t["domain"], "color": t["color"], "comment": t["comment"],
            "column_count": len(t["columns"]), "primary_key": t["primary_key"], "fk_count": len(t["foreign_keys"]),
            "referenced_by_count": len(t["referenced_by"]), "index_count": len(t["indexes"]), "row_count": t["row_count"],
            "columns": [{"name": c["name"], "type": c["type"], "not_null": c["not_null"],
                         "pk": c["name"] in t["primary_key"], "fk": any(c["name"] in fk["from_columns"] for fk in t["foreign_keys"])}
                        for c in t["columns"]]}


async def add_row_counts(db: AsyncSession, catalog: dict[str, Any]) -> None:
    for t in catalog["tables"].values():
        try:
            t["row_count"] = (await db.execute(text(f"SELECT count(*) FROM {q(t['schema'])}.{q(t['name'])}"))).scalar()
        except Exception:
            await db.rollback()
            t["row_count"] = None


def relational_notation(t: dict[str, Any]) -> dict[str, Any]:
    fk_cols = {c for fk in t["foreign_keys"] for c in fk["from_columns"]}
    uniq = {c for u in t["unique"] for c in u["columns"]}
    parts = []
    for c in t["columns"]:
        n = c["name"]
        parts.append(f"PK:{n}" if n in t["primary_key"] else f"FK:{n}" if n in fk_cols else n)
    return {"table": t["key"], "notation": f"{t['name'].upper()}({', '.join(parts)})", "primary_key": t["primary_key"],
            "foreign_keys": [{"columns": fk["from_columns"], "references": f"{fk['to_table']}({', '.join(fk['to_columns'])})",
                              "on_delete": fk["on_delete"]} for fk in t["foreign_keys"]],
            "unique": [u["columns"] for u in t["unique"]], "not_null": [c["name"] for c in t["columns"] if c["not_null"] and c["name"] not in t["primary_key"]],
            "checks": [c["definition"] for c in t["checks"]], "unique_columns": sorted(uniq)}


def normalization(catalog: dict[str, Any]) -> dict[str, Any]:
    """What the schema alone can and cannot prove. Functional dependencies are not stored in the catalog, so 3NF is never asserted."""
    rows = []
    for t in catalog["tables"].values():
        types = [c["type"] for c in t["columns"]]
        multivalued = [c["name"] for c in t["columns"] if c["type"].endswith("[]") or c["type"] in ("jsonb", "json", "tsvector")]
        candidate_keys = [t["primary_key"]] + [u["columns"] for u in t["unique"]]
        composite = [k for k in candidate_keys if len(k) > 1]
        redundancy = []
        for fk in t["foreign_keys"]:
            target = catalog["tables"].get(fk["to_table"])
            if not target:
                continue
            target_cols = {c["name"] for c in target["columns"]} - set(target["primary_key"]) - GENERIC_COLUMNS
            for col in t["columns"]:
                if col["name"] in target_cols and col["name"] not in t["primary_key"] and col["name"] not in {c for f in t["foreign_keys"] for c in f["from_columns"]}:
                    redundancy.append({"column": col["name"], "also_in": fk["to_table"], "via": fk["name"]})
        rows.append({
            "table": t["key"],
            "has_primary_key": bool(t["primary_key"]),
            "atomic_scalar_columns": len(types) - len(multivalued),
            "non_atomic_candidates": multivalued,
            "first_nf": "no primary key - not a proper relation" if not t["primary_key"] else
                        ("holds if the listed array/JSON columns are treated as opaque values (not repeating groups)" if multivalued else "holds (all columns are single-valued scalars; primary key present)"),
            "composite_candidate_keys": composite,
            "second_nf": "holds: no composite candidate key, so no partial dependency is possible" if not composite else
                         "needs functional-dependency analysis: a composite candidate key exists",
            "third_nf": "cannot be established from the schema alone (functional dependencies are not recorded)",
            "possible_redundancy": redundancy,
        })
    return {"tables": rows,
            "notes": ["First normal form is checked structurally; JSON/array/tsvector columns are flagged for review rather than counted as violations.",
                      "Second normal form is automatic for tables whose candidate keys are all single columns.",
                      "Third normal form needs the real functional dependencies; this page does not claim it. 'possible_redundancy' entries are "
                      "recommendations to review, not confirmed defects."],
            "summary": {"tables": len(rows), "without_primary_key": sum(1 for r in rows if not r["has_primary_key"]),
                        "with_composite_candidate_key": sum(1 for r in rows if r["composite_candidate_keys"]),
                        "with_possible_redundancy": sum(1 for r in rows if r["possible_redundancy"]),
                        "with_non_atomic_candidates": sum(1 for r in rows if r["non_atomic_candidates"])}}


def example_joins(catalog: dict[str, Any], key: str) -> list[dict[str, str]]:
    t = catalog["tables"][key]
    out = []
    for fk in t["foreign_keys"]:
        on = " AND ".join(f"a.{q(c)} = b.{q(rc)}" for c, rc in zip(fk["from_columns"], fk["to_columns"], strict=False))
        sch, tb = key.split(".")
        rs, rt = fk["to_table"].split(".")
        out.append({"direction": "references", "relationship": fk["name"],
                    "sql": f"SELECT a.*, b.*\nFROM {q(sch)}.{q(tb)} a\nJOIN {q(rs)}.{q(rt)} b ON {on}\nLIMIT 10;"})
    for ref in t["referenced_by"][:6]:
        src = catalog["tables"][ref["table"]]
        fk = next(f for f in src["foreign_keys"] if f["name"] == ref["constraint"])
        on = " AND ".join(f"b.{q(c)} = a.{q(rc)}" for c, rc in zip(fk["from_columns"], fk["to_columns"], strict=False))
        sch, tb = key.split(".")
        rs, rt = ref["table"].split(".")
        out.append({"direction": "referenced by", "relationship": ref["constraint"],
                    "sql": f"SELECT a.*, b.*\nFROM {q(sch)}.{q(tb)} a\nJOIN {q(rs)}.{q(rt)} b ON {on}\nLIMIT 10;"})
    return out


async def sample_rows(db: AsyncSession, t: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    if t["key"] not in SAMPLE_ALLOWED:
        return {"available": False, "reason": "Rows of this table may contain personal or operational data, so no sample is shown."}
    keep = [c["name"] for c in t["columns"]
            if not SENSITIVE_COLUMN.search(c["name"]) and not any(c["type"].startswith(b) for b in BULKY_TYPES)]
    if not keep:
        return {"available": False, "reason": "No displayable columns."}
    order = ", ".join(q(c) for c in (t["primary_key"] or keep[:1]))
    rows = (await db.execute(text(f"SELECT {', '.join(q(c) for c in keep)} FROM {q(t['schema'])}.{q(t['name'])} ORDER BY {order} LIMIT {int(limit)}"))).fetchall()
    def cell(v: Any) -> Any:
        if v is None or isinstance(v, (int, float, bool)):
            return v
        s = str(v)
        return s if len(s) <= 120 else s[:117] + "..."
    removed = [c["name"] for c in t["columns"] if c["name"] not in keep]
    return {"available": True, "columns": keep, "rows": [[cell(v) for v in r] for r in rows], "hidden_columns": removed,
            "note": "First rows by primary key. Sensitive-looking and bulky columns are hidden. Seeded catalogue records are provisional, not official."}


# ───────────────────────────────────────── components ─────────────────────────────────────────
def pg_display_name(version: str | None) -> str:
    """'PostgreSQL 16.4' from either platform's long version() string (Linux builds append distribution and compiler)."""
    m = re.match(r"\s*PostgreSQL\s+(\d+(?:\.\d+)*)", version or "")
    return f"PostgreSQL {m.group(1)}" if m else "PostgreSQL"


async def components(db: AsyncSession, catalog: dict[str, Any]) -> dict[str, Any]:
    health = await get_health_status()
    svc = health["services"]
    ext = {r[0]: r[1] for r in (await db.execute(text("SELECT extname, extversion FROM pg_extension"))).fetchall()}
    version = (await db.execute(text("SELECT version()"))).scalar() or ""
    pg_short = pg_display_name(version)
    spatial = [f"{t['key']}.{c['name']}" for t in catalog["tables"].values() for c in t["columns"] if c["type"].startswith(("geometry", "geography"))]
    vector = [f"{t['key']}.{c['name']}" for t in catalog["tables"].values() for c in t["columns"] if c["type"].startswith("vector")]

    def state(name: str) -> str:
        s = svc.get(name, {}).get("status")
        return {"healthy": "active", "disabled": "disabled", "unhealthy": "unavailable"}.get(s, "unknown")

    nodes = [
        {"id": "frontend", "name": "Next.js frontend", "layer": "client", "role": "primary", "status": "active",
         "purpose": "Browser UI for citizens, officers and administrators.", "location": "frontend/src (app routes, lib/api.ts)",
         "tables": [], "endpoints": ["/api/v1/*"], "connects_to": ["api"]},
        {"id": "api", "name": "FastAPI backend", "layer": "application", "role": "primary", "status": "active",
         "purpose": "REST API: authentication, role checks, validation, business rules.", "location": "backend/app/api/v1, backend/app/main.py",
         "tables": [], "endpoints": ["/api/v1/*", "/health"], "connects_to": ["services"]},
        {"id": "services", "name": "Service / data-access layer", "layer": "application", "role": "primary", "status": "active",
         "purpose": "Business logic and parameterised SQL through SQLAlchemy (async) on the asyncpg driver; no ORM models.",
         "location": "backend/app/services, backend/app/core/database.py", "tables": [], "endpoints": [], "connects_to": ["postgresql", "redis", "minio"]},
        {"id": "postgresql", "name": pg_short or "PostgreSQL", "layer": "data", "role": "primary storage", "status": "active",  # this very session just read its catalog
         "purpose": "System of record: catalogue, identities, complaints, documents, audit trail, provenance.",
         "location": "database/schema/001_schema.sql + database/migrations", "tables": sorted(catalog["tables"]),
         "endpoints": [], "connects_to": ["postgis", "pgvector"], "extensions": ext},
        {"id": "postgis", "name": "PostGIS", "layer": "data", "role": "extension", "status": "active" if "postgis" in ext else "not installed",
         "version": ext.get("postgis"), "purpose": "Spatial columns and jurisdiction resolution (point-in-polygon).",
         "location": "database/migrations/005_spatial_fixes_postgis.sql; backend/app/services/gis_service.py", "tables": sorted({c.rsplit(".", 1)[0] for c in spatial}),
         "endpoints": ["/api/v1/gis/*"], "connects_to": ["postgresql"], "columns": spatial},
        {"id": "pgvector", "name": "pgvector", "layer": "data", "role": "extension", "status": "active" if "vector" in ext else "not installed",
         "version": ext.get("vector"), "purpose": "Embedding columns and HNSW similarity search for assistant retrieval.",
         "location": "backend/app/ai (embeddings, retrieval)", "tables": sorted({c.rsplit(".", 1)[0] for c in vector}),
         "endpoints": ["/api/v1/chat/message"], "connects_to": ["postgresql"], "columns": vector},
        {"id": "neo4j", "name": "Neo4j", "layer": "data", "role": "optional projection", "status": state("neo4j"),
         "purpose": "Disposable analytic graph projected from PostgreSQL; nothing in the core application depends on it.",
         "location": "backend/knowledge_graph/rebuild.py (python -m knowledge_graph.rebuild)", "tables": [],
         "endpoints": ["/api/v1/admin/knowledge-graph/stats"], "connects_to": ["postgresql"],
         "note": "Flow is PostgreSQL -> Neo4j only (rebuild job); the API only reads statistics."},
        {"id": "redis", "name": "Redis", "layer": "data", "role": "optional (configured, health-checked)", "status": state("redis"),
         "purpose": "Configured and health-checked. Rate limiting is currently in-process and token revocation is future work, so no feature stores data in Redis yet.",
         "location": "backend/app/core/health.py; backend/app/security/ratelimit.py (documents the in-process limitation)",
         "tables": [], "endpoints": ["/health"], "connects_to": []},
        {"id": "minio", "name": "MinIO / object storage", "layer": "data", "role": "optional (not used by any feature yet)", "status": state("minio"),
         "purpose": "Reserved for complaint evidence files. Evidence upload is intentionally not implemented (API answers 503).",
         "location": "docker-compose.yml (profile 'storage'); backend/app/core/health.py", "tables": [], "endpoints": ["/api/v1/complaints/{id}/evidence"], "connects_to": []},
    ]
    edges = [
        {"from": "frontend", "to": "api", "label": "HTTPS + JSON (JWT bearer token)", "kind": "primary"},
        {"from": "api", "to": "services", "label": "function calls, role checks first", "kind": "primary"},
        {"from": "services", "to": "postgresql", "label": "parameterised SQL (asyncpg)", "kind": "primary"},
        {"from": "postgresql", "to": "postgis", "label": "spatial types, GiST indexes", "kind": "extension"},
        {"from": "postgresql", "to": "pgvector", "label": "vector columns, HNSW indexes", "kind": "extension"},
        {"from": "postgresql", "to": "neo4j", "label": "rebuild job copies a projection (one way)", "kind": "optional"},
        {"from": "services", "to": "redis", "label": "health check only", "kind": "optional"},
        {"from": "services", "to": "minio", "label": "health check only (storage not implemented)", "kind": "optional"},
    ]
    return {"nodes": nodes, "edges": edges, "legend": {"primary": "required data path", "extension": "PostgreSQL extension", "optional": "optional / supporting service"},
            "feature_flags": {"FEATURE_GRAPH": settings.FEATURE_GRAPH, "FEATURE_VECTOR_SEARCH": settings.FEATURE_VECTOR_SEARCH},
            "demo_data_included": settings.DEMO_INCLUDE_SYNTHETIC}


# ───────────────────────────────────────── advanced concepts ─────────────────────────────────────────
def _scan(patterns: list[str], folders: tuple[str, ...] = ("app", "scripts", "etl", "knowledge_graph")) -> list[str]:
    hits: set[str] = set()
    regs = [re.compile(p) for p in patterns]
    for folder in folders:
        for path in (BACKEND_DIR / folder).rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "architecture_service.py":
                continue
            try:
                body = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if any(r.search(body) for r in regs):
                hits.add(path.relative_to(BACKEND_DIR).as_posix())
    return sorted(hits)


async def advanced(db: AsyncSession, catalog: dict[str, Any]) -> dict[str, Any]:
    schemas = catalog["schemas"]
    views = [dict(r._mapping) for r in (await db.execute(text(
        "SELECT schemaname AS schema, viewname AS name, left(definition, 1800) AS definition FROM pg_views WHERE schemaname = ANY(:s) ORDER BY 1, 2"), {"s": schemas})).fetchall()]
    funcs = [dict(r._mapping) for r in (await db.execute(text("""
        SELECT n.nspname AS schema, p.proname AS name, pg_get_function_arguments(p.oid) AS arguments, pg_get_function_result(p.oid) AS returns,
               l.lanname AS language, left(pg_get_functiondef(p.oid), 1800) AS definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_language l ON l.oid = p.prolang
        WHERE n.nspname = ANY(:s) AND p.prokind = 'f' AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
        ORDER BY 1, 2"""), {"s": schemas})).fetchall()]
    triggers = [dict(r._mapping) for r in (await db.execute(text("""
        SELECT n.nspname || '.' || c.relname AS "table", t.tgname AS name, p.proname AS function, pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE NOT t.tgisinternal AND n.nspname = ANY(:s) ORDER BY 1, 2"""), {"s": schemas})).fetchall()]
    methods: dict[str, list[dict[str, str]]] = defaultdict(list)
    for t in catalog["tables"].values():
        for i in t["indexes"]:
            methods[i["method"]].append({"table": t["key"], "index": i["name"], "definition": i["definition"]})
    constraint_counts = {
        "primary_key": sum(1 for t in catalog["tables"].values() if t["primary_key"]),
        "foreign_key": len(catalog["foreign_keys"]),
        "unique": sum(len(t["unique"]) for t in catalog["tables"].values()),
        "check": sum(len(t["checks"]) for t in catalog["tables"].values()),
        "not_null_columns": sum(1 for t in catalog["tables"].values() for c in t["columns"] if c["not_null"]),
    }
    exts = [dict(r._mapping) for r in (await db.execute(text("SELECT extname AS name, extversion AS version FROM pg_extension ORDER BY 1"))).fetchall()]
    spatial_cols = [{"table": t["key"], "column": c["name"], "type": c["type"]} for t in catalog["tables"].values() for c in t["columns"] if c["type"].startswith(("geometry", "geography"))]
    vector_cols = [{"table": t["key"], "column": c["name"], "type": c["type"]} for t in catalog["tables"].values() for c in t["columns"] if c["type"].startswith("vector")]
    history = []
    for key in ("complaints.complaint_history", "audit.audit_log", "system.verification_status_log"):
        t = catalog["tables"].get(key)
        if t:
            history.append({"table": key, "rows": t["row_count"], "purpose": {"complaints.complaint_history": "status timeline of every complaint (written by a trigger)",
                            "audit.audit_log": "who did what, when (no secrets stored)", "system.verification_status_log": "every change of a record's verification status"}[key]})
    tx_files = _scan([r"FOR UPDATE", r"begin_nested", r"\.rollback\(\)"])
    concept = lambda name, implemented, summary, location, examples=None: {  # noqa: E731
        "concept": name, "status": "Implemented" if implemented else "Not implemented", "summary": summary, "location": location, "examples": examples or []}
    return {"concepts": [
        concept("Views", bool(views), f"{len(views)} application view(s)." if views else "No application views.", "database/schema/001_schema.sql", views),
        concept("Stored functions", bool(funcs), f"{len(funcs)} PL/pgSQL function(s) defined by the project." if funcs else "No project functions.", "database/schema, database/migrations", funcs),
        concept("Stored procedures (CALL)", False, "The project uses functions and triggers; no SQL PROCEDUREs are defined.", "-"),
        concept("Triggers", bool(triggers), f"{len(triggers)} trigger(s), e.g. complaint status history and verification logging." if triggers else "No triggers.", "database/schema, database/migrations", triggers),
        concept("Transactions and rollback", bool(tx_files), "Request-scoped sessions roll back on error; savepoints (begin_nested) isolate optional writes; FOR UPDATE row locks guard status changes and scheduler claims.", ", ".join(tx_files[:6]) or "-"),
        concept("Indexing strategies", True, "B-tree for keys/lookups, GIN for text search and trigrams, GiST for spatial/exclusion constraints, HNSW for vector search: " + ", ".join(f"{m}: {len(v)}" for m, v in sorted(methods.items())),
                "database/schema/001_schema.sql", [{"method": m, "count": len(v), "examples": v[:3]} for m, v in sorted(methods.items())]),
        concept("Query plans", True, "EXPLAIN (without executing) is available for each example query in the Implementation tab.", "backend/app/api/v1/architecture.py"),
        concept("PostGIS spatial queries", "postgis" in {e["name"] for e in exts}, "Spatial columns and a jurisdiction-resolution function; real boundary polygons are NOT loaded (tests use synthetic boxes).", "database/migrations/005_spatial_fixes_postgis.sql", spatial_cols),
        concept("pgvector similarity search", "vector" in {e["name"] for e in exts}, "Embedding columns with HNSW indexes; retrieval ranks by cosine distance with a similarity floor.", "backend/app/ai", vector_cols),
        concept("Neo4j graph relationships", True, "Optional projection of departments, schemes, services, authorities, categories and complaints; rebuilt from PostgreSQL (one way).", "backend/knowledge_graph/rebuild.py"),
        concept("Redis", False, "Configured and health-checked only. Rate limits are in-process and token revocation is not implemented, so Redis stores no application data yet.", "backend/app/security/ratelimit.py"),
        concept("Data integrity constraints", True, f"{constraint_counts['primary_key']} primary keys, {constraint_counts['foreign_key']} foreign keys, {constraint_counts['unique']} unique and {constraint_counts['check']} check constraints.", "database/schema/001_schema.sql", [constraint_counts]),
        concept("Audit and history records", True, "Append-only trails for complaints, security-relevant actions and verification-status changes.", "audit.audit_log, complaints.complaint_history, system.verification_status_log", history),
    ], "extensions": exts, "constraint_counts": constraint_counts}


# ───────────────────────────────────────── curated, runnable examples ─────────────────────────────────────────
EXAMPLES: list[dict[str, Any]] = [
    {"id": "schemes_by_department", "title": "Schemes with their department", "tables": ["schemes.scheme", "administration.department"],
     "relationships": ["scheme.department_id -> department.department_id"],
     "purpose": "Follow a many-to-one foreign key from a scheme to the department that administers it.",
     "result": "One row per scheme: its name, department and verification status (all seeded records are provisional).",
     "sql": "SELECT s.scheme_code, s.scheme_name, d.department_name, s.verification_status\nFROM schemes.scheme s\nJOIN administration.department d ON d.department_id = s.department_id\nORDER BY s.scheme_name\nLIMIT 20"},
    {"id": "services_by_department", "title": "Services per department", "tables": ["services.service", "administration.department"],
     "relationships": ["service.department_id -> department.department_id"],
     "purpose": "Aggregate over a foreign key.", "result": "Number of catalogue services per department.",
     "sql": "SELECT d.department_name, count(*) AS services\nFROM services.service s\nJOIN administration.department d ON d.department_id = s.department_id\nGROUP BY d.department_name\nORDER BY services DESC, d.department_name\nLIMIT 20"},
    {"id": "category_routing", "title": "How complaint categories are routed", "tables": ["complaints.routing_rule", "complaints.complaint_category", "administration.department"],
     "relationships": ["routing_rule.category_id -> complaint_category", "routing_rule.department_id -> department"],
     "purpose": "A three-table join showing which department receives each complaint category.", "result": "Routing rules ordered by category and priority.",
     "sql": "SELECT c.category_name, r.jurisdiction_level, d.department_name, r.priority_order\nFROM complaints.routing_rule r\nJOIN complaints.complaint_category c ON c.category_id = r.category_id\nJOIN administration.department d ON d.department_id = r.department_id\nORDER BY c.category_name, r.priority_order\nLIMIT 25"},
    {"id": "authority_hierarchy", "title": "Authority escalation chain (self-reference)", "tables": ["administration.authority", "administration.department"],
     "relationships": ["authority.parent_authority_id -> authority.authority_id (self)", "authority.department_id -> department"],
     "purpose": "A self-referencing foreign key models the escalation hierarchy.", "result": "Each authority with its parent (NULL for top-level routing placeholders).",
     "sql": "SELECT a.authority_name, p.authority_name AS escalates_to, d.department_name\nFROM administration.authority a\nLEFT JOIN administration.authority p ON p.authority_id = a.parent_authority_id\nJOIN administration.department d ON d.department_id = a.department_id\nORDER BY d.department_name, a.authority_name\nLIMIT 20"},
    {"id": "complaints_by_status", "title": "Complaints per department and status (counts only)", "tables": ["complaints.complaint", "administration.department"],
     "relationships": ["complaint.department_id -> department.department_id"],
     "purpose": "Aggregate query behind the dashboards; returns counts only, never complaint text.", "result": "Counts include clearly labelled synthetic demo complaints when demo mode is on.",
     "sql": "SELECT d.department_name, c.status, count(*) AS complaints\nFROM complaints.complaint c\nJOIN administration.department d ON d.department_id = c.department_id\nGROUP BY d.department_name, c.status\nORDER BY d.department_name, complaints DESC\nLIMIT 25"},
    {"id": "status_history", "title": "Status transitions recorded by the history trigger", "tables": ["complaints.complaint_history"], "relationships": ["complaint_history.complaint_id -> complaint"],
     "purpose": "Counts of old -> new status pairs written by the trg_complaint_history trigger.", "result": "How complaints moved through the state machine.",
     "sql": "SELECT old_status, new_status, count(*) AS transitions\nFROM complaints.complaint_history\nGROUP BY old_status, new_status\nORDER BY transitions DESC\nLIMIT 25"},
    {"id": "eligibility_rules_per_scheme", "title": "Eligibility rules per scheme", "tables": ["schemes.scheme", "schemes.eligibility_rule"], "relationships": ["eligibility_rule.scheme_id -> scheme.scheme_id"],
     "purpose": "One-to-many relationship: a scheme has many rules; groups combine with OR, rules in a group with AND.", "result": "Rule and group counts. Rules shown here are labelled demonstration rules, not official criteria.",
     "sql": "SELECT s.scheme_name, count(r.rule_id) AS rules, count(DISTINCT r.rule_group) AS rule_groups\nFROM schemes.scheme s\nLEFT JOIN schemes.eligibility_rule r ON r.scheme_id = s.scheme_id\nGROUP BY s.scheme_name\nORDER BY rules DESC, s.scheme_name\nLIMIT 20"},
    {"id": "verification_summary", "title": "Verification status of catalogue records", "tables": ["schemes.scheme", "services.service", "administration.department"], "relationships": [],
     "purpose": "Data-provenance check: how many records are verified vs provisional.", "result": "Nothing is official_verified until a source document is recorded.",
     "sql": "SELECT 'scheme' AS kind, verification_status, count(*) AS records FROM schemes.scheme GROUP BY verification_status\nUNION ALL SELECT 'service', verification_status, count(*) FROM services.service GROUP BY verification_status\nUNION ALL SELECT 'department', verification_status, count(*) FROM administration.department GROUP BY verification_status\nORDER BY 1, 2"},
    {"id": "vector_coverage", "title": "pgvector: embedding coverage (counts only)", "tables": ["documents.document_chunk"], "relationships": ["document_chunk.document_id -> document"],
     "purpose": "How many document chunks have an embedding. A similarity search would use  ORDER BY embedding <=> $query_vector  on the HNSW index.", "result": "Zero chunks until documents are ingested and embedded.",
     "sql": "SELECT coalesce(embedding_model, '(none)') AS embedding_model, count(*) AS chunks, count(embedding) AS embedded\nFROM documents.document_chunk\nGROUP BY embedding_model\nORDER BY chunks DESC\nLIMIT 10"},
    {"id": "postgis_boundaries", "title": "PostGIS: district boundary coverage", "tables": ["administration.district"], "relationships": [],
     "purpose": "Spatial column check; resolve_jurisdiction() can only work for districts that have a polygon.", "result": "Real boundary polygons are not loaded, so the count is normally 0.",
     "sql": "SELECT count(*) AS districts, count(geometry) AS with_boundary_polygon,\n       count(*) FILTER (WHERE geometry IS NOT NULL AND ST_IsValid(geometry)) AS valid_polygons\nFROM administration.district"},
]


def example_by_id(example_id: str) -> dict[str, Any] | None:
    return next((e for e in EXAMPLES if e["id"] == example_id), None)


async def run_example(db: AsyncSession, example: dict[str, Any]) -> dict[str, Any]:
    await db.execute(text("SET TRANSACTION READ ONLY"))
    await db.execute(text("SET LOCAL statement_timeout = '3000'"))
    try:
        res = await db.execute(text(example["sql"]))
        rows = res.fetchall()
        return {"columns": list(res.keys()), "rows": [[v if isinstance(v, (int, float, bool)) or v is None else str(v) for v in r] for r in rows], "row_count": len(rows)}
    finally:
        await db.rollback()


async def explain_example(db: AsyncSession, example: dict[str, Any]) -> dict[str, Any]:
    await db.execute(text("SET TRANSACTION READ ONLY"))
    await db.execute(text("SET LOCAL statement_timeout = '3000'"))
    try:
        res = await db.execute(text("EXPLAIN " + example["sql"]))   # plan only: the statement is not executed
        return {"plan": [r[0] for r in res.fetchall()]}
    finally:
        await db.rollback()
