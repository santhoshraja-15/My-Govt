"""Admin service — database intelligence console backend."""
import re
import time
from typing import Any, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.health import get_health_status

logger = structlog.get_logger(__name__)

# SQL keywords that are NOT allowed in the query workspace
_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE"
    r"|EXEC|EXECUTE|COPY|\\|pg_read_file|pg_ls_dir|lo_import|lo_export"
    r"|dblink|openquery|SET\s+ROLE|SET\s+SESSION)\b",
    re.IGNORECASE,
)


_IDENT = re.compile(r"[a-z_][a-z0-9_]{0,62}")
# Columns never returned by the admin console (credentials / secrets)
_SENSITIVE_COLUMNS = frozenset({"password_hash", "token_hash", "secret", "api_key"})


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self) -> dict:
        """Platform overview. Every figure is a live COUNT; synthetic (generated) complaints and
        citizens are excluded from business metrics and reported separately."""
        queries = {
            "schemas": "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')",
            "tables": "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema','pg_toast') AND table_type='BASE TABLE'",
            "indexes": "SELECT count(*) FROM pg_indexes WHERE schemaname NOT IN ('pg_catalog','information_schema')",
            "foreign_keys": "SELECT count(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY'",
            "datasets": "SELECT count(*) FROM system.dataset_registry",
            "sources": "SELECT count(*) FROM system.source_registry",
        }
        overview: dict = {}
        for key, sql in queries.items():
            try:
                r = await self.db.execute(text(sql))
                overview[key] = r.scalar() or 0
            except Exception:
                overview[key] = None
        biz = {
            "schemes": "SELECT count(*) FROM schemes.scheme WHERE status='active'",
            "services": "SELECT count(*) FROM services.service WHERE status='active'",
            "departments": "SELECT count(*) FROM administration.department WHERE status='active'",
            "districts": "SELECT count(*) FROM administration.district",
            "documents": "SELECT count(*) FROM documents.document",
            "complaints_total": "SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic",
            "complaints_open": "SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic AND status NOT IN ('resolved','closed','rejected')",
            "complaints_sla_breached": "SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic AND due_date < now() AND status NOT IN ('resolved','closed','rejected')",
            "complaints_unassigned": "SELECT count(*) FROM complaints.complaint WHERE NOT is_synthetic AND authority_id IS NULL AND status NOT IN ('resolved','closed','rejected')",
            "synthetic_complaints": "SELECT count(*) FROM complaints.complaint WHERE is_synthetic",
        }
        stats: dict = {}
        for key, sql in biz.items():
            try:
                stats[key] = (await self.db.execute(text(sql))).scalar() or 0
            except Exception:
                stats[key] = None
        verification: dict = {}
        for label, tbl in (("schemes", "schemes.scheme"), ("services", "services.service"),
                           ("departments", "administration.department"), ("districts", "administration.district")):
            try:
                rows = (await self.db.execute(text(f"SELECT verification_status, count(*) FROM {tbl} GROUP BY 1"))).fetchall()
                verification[label] = {r[0]: r[1] for r in rows}
            except Exception:
                verification[label] = None
        overview["database_stats"] = stats
        overview["verification"] = verification
        return overview

    async def get_connection_status(self) -> dict:
        health = await get_health_status(detailed=True)
        # Enrich with extension info
        try:
            ext_result = await self.db.execute(text(
                "SELECT extname, extversion FROM pg_extension ORDER BY extname"
            ))
            extensions = [{"name": r[0], "version": r[1]} for r in ext_result.fetchall()]
        except Exception:
            extensions = []

        return {
            "services": health["services"],
            "postgresql_extensions": extensions,
        }

    async def list_schemas(self) -> list:
        result = await self.db.execute(text("""
            SELECT s.schema_name,
                   count(DISTINCT t.table_name) FILTER (WHERE t.table_type='BASE TABLE') AS table_count,
                   count(DISTINCT t.table_name) FILTER (WHERE t.table_type='VIEW') AS view_count
            FROM information_schema.schemata s
            LEFT JOIN information_schema.tables t ON t.table_schema = s.schema_name
            WHERE s.schema_name NOT IN ('pg_catalog','information_schema','pg_toast','pg_temp_1','pg_toast_temp_1')
            GROUP BY s.schema_name
            ORDER BY s.schema_name
        """))
        return [
            {"schema_name": r[0], "table_count": r[1] or 0, "view_count": r[2] or 0}
            for r in result.fetchall()
        ]

    async def list_tables(self, schema_name: str) -> list:
        result = await self.db.execute(text("""
            SELECT t.table_name, t.table_type,
                   obj_description(pc.oid, 'pg_class') AS description,
                   pc.reltuples::bigint AS estimated_rows
            FROM information_schema.tables t
            LEFT JOIN pg_class pc ON pc.relname = t.table_name
            LEFT JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = t.table_schema
            WHERE t.table_schema = :schema
            ORDER BY t.table_name
        """), {"schema": schema_name})
        return [
            {
                "table_name": r[0],
                "table_type": r[1],
                "description": r[2],
                "estimated_rows": max(r[3], 0) if r[3] else 0,
            }
            for r in result.fetchall()
        ]

    async def get_table_detail(self, schema_name: str, table_name: str) -> dict:
        # Columns
        col_result = await self.db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default,
                   character_maximum_length, numeric_precision
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY ordinal_position
        """), {"schema": schema_name, "table": table_name})
        columns = [
            {
                "name": r[0], "type": r[1], "nullable": r[2] == "YES",
                "default": r[3], "max_length": r[4], "precision": r[5],
            }
            for r in col_result.fetchall()
        ]

        # Indexes
        idx_result = await self.db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = :schema AND tablename = :table
            ORDER BY indexname
        """), {"schema": schema_name, "table": table_name})
        indexes = [{"name": r[0], "definition": r[1]} for r in idx_result.fetchall()]

        # Constraints
        con_result = await self.db.execute(text("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_schema = :schema AND table_name = :table
            ORDER BY constraint_type, constraint_name
        """), {"schema": schema_name, "table": table_name})
        constraints = [{"name": r[0], "type": r[1]} for r in con_result.fetchall()]

        # Row count estimate
        rc = await self.db.execute(text("""
            SELECT reltuples::bigint FROM pg_class
            WHERE relname = :table AND relnamespace = (
                SELECT oid FROM pg_namespace WHERE nspname = :schema
            )
        """), {"schema": schema_name, "table": table_name})
        row_count = rc.scalar() or 0

        return {
            "schema_name": schema_name,
            "table_name": table_name,
            "columns": columns,
            "indexes": indexes,
            "constraints": constraints,
            "estimated_rows": max(row_count, 0),
        }

    async def get_table_sample(self, schema_name: str, table_name: str,
                                limit: int = 20, offset: int = 0) -> dict:
        # Safety: only allow known schemas
        allowed_schemas = [
            "system", "administration", "identity", "schemes",
            "services", "policies", "documents", "complaints", "ai", "audit"
        ]
        if schema_name not in allowed_schemas:
            return {"error": "Schema not accessible", "rows": [], "columns": []}

        if not _IDENT.fullmatch(table_name):
            return {"error": "Invalid table name", "rows": [], "columns": []}
        exists = await self.db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = :t"),
            {"s": schema_name, "t": table_name},
        )
        if not exists.fetchone():
            return {"error": "Table not found", "rows": [], "columns": []}
        safe_table = f'"{schema_name}"."{table_name}"'
        try:
            count_r = await self.db.execute(text(f"SELECT count(*) FROM {safe_table}"))
            total = count_r.scalar() or 0

            result = await self.db.execute(
                text(f"SELECT * FROM {safe_table} LIMIT :lim OFFSET :off"),
                {"lim": limit, "off": offset},
            )
            rows = result.fetchall()
            columns = list(result.keys()) if rows else []

            serialized = []
            for row in rows:
                serialized.append({
                    col: ("[REDACTED]" if col in _SENSITIVE_COLUMNS
                          else str(val) if not isinstance(val, (str, int, float, bool, type(None))) else val)
                    for col, val in zip(columns, row, strict=True)
                })

            return {"total": total, "columns": columns, "rows": serialized,
                    "limit": limit, "offset": offset}
        except Exception as e:
            return {"error": str(e), "rows": [], "columns": []}

    async def get_relationships(self, schema_name: Optional[str] = None) -> list:
        where = "AND kcu.table_schema = :schema" if schema_name else ""
        params: dict = {}
        if schema_name:
            params["schema"] = schema_name

        result = await self.db.execute(text(f"""
            SELECT
                kcu.table_schema || '.' || kcu.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_schema || '.' || ccu.table_name AS to_table,
                ccu.column_name AS to_column,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              {where}
            ORDER BY from_table, from_column
        """), params)

        return [
            {
                "from_table": r[0], "from_column": r[1],
                "to_table": r[2], "to_column": r[3],
                "constraint_name": r[4],
            }
            for r in result.fetchall()
        ]

    async def run_safe_query(self, sql: str) -> dict:
        """Execute a read-only SQL statement with safety checks."""
        sql = sql.strip().rstrip(";")
        if not sql:
            return {"error": "Empty query"}
        if _FORBIDDEN_SQL.search(sql):
            return {"error": "Mutating or unsafe SQL statements are not allowed in the query workspace."}
        if ";" in sql:
            return {"error": "Multiple statements are not allowed."}
        if not re.match(r"(?is)^\s*(select|with|explain|show|table)\b", sql):
            return {"error": "Only read-only SELECT queries are allowed."}
        if re.search(r"(?i)password_hash|token_hash", sql):
            return {"error": "Credential columns cannot be queried."}
        if len(sql) > 5000:
            return {"error": "Query too long (max 5000 chars)."}
        try:
            # Defence in depth beyond the keyword filter: a READ ONLY transaction rejects writes.
            await self.db.execute(text("SET TRANSACTION READ ONLY"))
            await self.db.execute(text("SET LOCAL statement_timeout = '10s'"))
            started = time.perf_counter()
            result = await self.db.execute(text(sql))
            rows = result.fetchmany(500)
            columns = list(result.keys()) if rows else []
            serialized = [
                {col: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
                 for col, v in zip(columns, row, strict=True)}
                for row in rows
            ]
            return {"columns": columns, "rows": serialized, "row_count": len(serialized),
                    "execution_time_ms": round((time.perf_counter() - started) * 1000, 1)}
        except Exception as e:
            return {"error": str(e)}
        finally:
            # end the READ ONLY transaction so later writes in this request (e.g. the audit row) work
            await self.db.rollback()

    async def list_datasets(self) -> list:
        try:
            r = await self.db.execute(text("""
                SELECT d.dataset_id, d.dataset_name, d.file_format,
                       d.download_date, d.record_count, d.processing_status,
                       d.validation_status, d.checksum_sha256,
                       s.source_name, s.source_type, s.reliability_score
                FROM system.dataset_registry d
                LEFT JOIN system.source_registry s ON s.source_id = d.source_id
                ORDER BY d.download_date DESC NULLS LAST
            """))
            return [dict(row._mapping) for row in r.fetchall()]
        except Exception:
            result = await self.db.execute(text("""
                SELECT dataset_id, dataset_name, file_format,
                       download_date, record_count, processing_status,
                       validation_status, checksum_sha256
                FROM system.dataset_registry
                ORDER BY download_date DESC NULLS LAST
            """))
            cols = list(result.keys())
            return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]

    async def list_sources(self) -> list:
        result = await self.db.execute(text("""
            SELECT source_id, source_code, source_name, source_type,
                   url, jurisdiction, reliability_score, license,
                   last_checked, status
            FROM system.source_registry
            ORDER BY source_name
        """))
        cols = list(result.keys())
        return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]

    async def get_audit_logs(self, limit: int = 50, offset: int = 0) -> dict:
        try:
            count_r = await self.db.execute(text("SELECT count(*) FROM audit.audit_log"))
            total = count_r.scalar() or 0
            result = await self.db.execute(text("""
                SELECT audit_id AS log_id,
                       user_id AS actor_id,
                       user_role AS actor_role,
                       action,
                       entity_type,
                       entity_id,
                       occurred_at AS created_at,
                       new_value ->> 'outcome' AS outcome,
                       ip_address::text AS ip_address
                FROM audit.audit_log
                ORDER BY occurred_at DESC
                LIMIT :lim OFFSET :off
            """), {"lim": limit, "off": offset})
            cols = list(result.keys())
            rows = [
                {col: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
                 for col, v in zip(cols, row, strict=True)}
                for row in result.fetchall()
            ]
            return {"total": total, "rows": rows, "limit": limit, "offset": offset}
        except Exception as e:
            return {"total": 0, "rows": [], "error": str(e)}

    async def get_data_quality_report(self) -> dict:
        try:
            result = await self.db.execute(text("""
                SELECT dataset_id, dataset_name, file_name,
                       quality_completeness,
                       quality_accuracy,
                       quality_consistency,
                       quality_freshness,
                       processing_status,
                       validation_status,
                       record_count
                FROM system.dataset_registry
                ORDER BY dataset_name
            """))
            cols = list(result.keys())
            return {"datasets": [dict(zip(cols, r, strict=True)) for r in result.fetchall()]}
        except Exception as e:
            return {"datasets": [], "error": str(e)}

    # ── operations: backlog, department performance, verification queue ─────────────────────────
    async def get_complaints(self, status: Optional[str] = None, overdue: bool = False, unassigned: bool = False,
                             limit: int = 50, offset: int = 0) -> dict:
        """Staff view of real (non-synthetic) complaints with the legal next statuses for each."""
        from app.services import complaint_rules as rules

        cond = ["NOT c.is_synthetic"]
        params: dict[str, Any] = {}
        if status:
            cond.append("c.status = :status")
            params["status"] = status
        if overdue:
            cond.append("c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected')")
        if unassigned:
            cond.append("c.authority_id IS NULL AND c.status NOT IN ('resolved','closed','rejected')")
        where = " AND ".join(cond)
        total = (await self.db.execute(text(f"SELECT count(*) FROM complaints.complaint c WHERE {where}"), params)).scalar() or 0
        rows = (await self.db.execute(text(f"""
            SELECT c.complaint_id::text AS complaint_id, c.complaint_ref AS reference_number, c.title, c.status, c.priority,
                   cat.category_name, d.department_name, a.authority_name, c.created_at, c.due_date,
                   (c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected')) AS sla_breached,
                   CASE WHEN c.authority_id IS NOT NULL THEN CASE WHEN a.is_routing_placeholder THEN 'department_level' ELSE 'authority_assigned' END
                        WHEN c.department_id IS NOT NULL THEN 'department_only' ELSE 'unassigned' END AS assignment_state
            FROM complaints.complaint c
            LEFT JOIN complaints.complaint_category cat ON cat.category_id = c.category_id
            LEFT JOIN administration.department d ON d.department_id = c.department_id
            LEFT JOIN administration.authority a ON a.authority_id = c.authority_id
            WHERE {where}
            ORDER BY (c.due_date < now()) DESC NULLS LAST, c.created_at DESC
            LIMIT :lim OFFSET :off"""), {**params, "lim": limit, "off": offset})).fetchall()
        items = []
        for r in rows:
            m = dict(r._mapping)
            m["allowed_next"] = list(rules.TRANSITIONS.get(m["status"], ()))
            items.append(m)
        return {"total": total, "items": items, "limit": limit, "offset": offset}

    async def get_department_performance(self) -> list:
        """Per-department workload from real complaints (synthetic excluded)."""
        r = await self.db.execute(text("""
            SELECT d.department_id, d.department_name,
                   count(c.complaint_id)::int AS total,
                   count(*) FILTER (WHERE c.status IN ('resolved','closed'))::int AS resolved,
                   count(*) FILTER (WHERE c.due_date < now() AND c.status NOT IN ('resolved','closed','rejected'))::int AS sla_breached,
                   count(*) FILTER (WHERE c.authority_id IS NULL AND c.status NOT IN ('resolved','closed','rejected'))::int AS without_authority,
                   round(extract(epoch FROM avg(c.resolved_at - c.created_at) FILTER (WHERE c.resolved_at IS NOT NULL)) / 3600.0, 1)::float AS avg_resolution_hours
            FROM administration.department d
            JOIN complaints.complaint c ON c.department_id = d.department_id AND NOT c.is_synthetic
            GROUP BY d.department_id, d.department_name
            ORDER BY sla_breached DESC, total DESC"""))
        return [dict(row._mapping) for row in r.fetchall()]

    async def get_verification_queue(self, limit: int = 200) -> dict:
        """Everything not yet official_verified, with its asserted (unconfirmed) reference, and recent status changes."""
        queue: list[dict] = []
        for label, tbl, key, name in (("scheme", "schemes.scheme", "scheme_code", "scheme_name"),
                                      ("service", "services.service", "service_code", "service_name"),
                                      ("department", "administration.department", "department_code", "department_name"),
                                      ("district", "administration.district", "district_code", "district_name")):
            rows = (await self.db.execute(text(
                f"SELECT '{label}' AS kind, {key} AS code, {name} AS name, verification_status, source_document_ref "
                f"FROM {tbl} WHERE verification_status <> 'official_verified' ORDER BY {key} LIMIT :n"), {"n": limit})).fetchall()
            queue.extend(dict(r._mapping) for r in rows)
        log = (await self.db.execute(text(
            "SELECT table_name, record_key, old_status, new_status, reason, changed_at FROM system.verification_status_log "
            "ORDER BY log_id DESC LIMIT 20"))).fetchall()
        return {"queue": queue, "recent_changes": [dict(r._mapping) for r in log]}
