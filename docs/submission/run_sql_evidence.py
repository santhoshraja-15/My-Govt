"""Run the lab's SQL operations against a SCRATCH database and record the real outputs.

    python run_sql_evidence.py --dsn postgresql://postgres@localhost:5432/mygovt_dev_report --out .

Writes sql_evidence.json (statement + output per step) and lab_queries.sql (the same script, runnable in psql).
The database must be a disposable copy (python -m scripts.demo_env --db mygovt_dev_report --reset): this script inserts,
updates and deletes rows and creates one illustrative stored procedure. Nothing is typed by hand: outputs are what PostgreSQL returned.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg

EVIDENCE: list[dict] = []
NOTICES: list[str] = []


def render(columns: list[str], rows: list[list[str]], tag: str) -> str:
    if not columns:
        return tag
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(columns)]
    head = " " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    rule = "-" + "-+-".join("-" * w for w in widths) + "-"
    body = [" " + " | ".join(r[i].ljust(widths[i]) for i in range(len(columns))) for r in rows]
    return "\n".join([head, rule, *body, f"({len(rows)} row{'s' if len(rows) != 1 else ''})"])


def cell(v: object) -> str:
    s = "NULL" if v is None else str(v)
    s = s.replace("\n", " ")
    return s if len(s) <= 58 else s[:55] + "..."


async def run(conn: asyncpg.Connection, sid: str, title: str, sql: str, section: str, expect_error: bool = False) -> list:
    NOTICES.clear()
    out, rows_out = "", []
    try:
        multi = sql.strip().rstrip(";").count(";") > 0 and "$$" not in sql
        stmt = None if multi else await conn.prepare(sql)
        cols = [] if multi else [a.name for a in stmt.get_attributes()]
        if multi:
            out = await conn.execute(sql)
        elif cols:
            recs = await stmt.fetch()
            rows_out = recs
            out = render(cols, [[cell(r[c]) for c in range(len(cols))] for r in recs], "")
        else:
            tag = await conn.execute(sql)
            out = tag
    except Exception as e:  # noqa: BLE001
        out = f"ERROR: {type(e).__name__}: {e}"
        if not expect_error:
            out += "   <-- unexpected"
    if NOTICES:
        out += "\n" + "\n".join(f"NOTICE: {n}" for n in NOTICES)
    EVIDENCE.append({"id": sid, "section": section, "title": title, "sql": sql.strip(), "output": out})
    print(f"[{sid}] {title}\n{out[:400]}\n")
    return list(rows_out)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    assert "report" in a.dsn or "dev" in a.dsn, "refusing to run DML against a non-scratch database"
    conn = await asyncpg.connect(a.dsn)
    conn.add_log_listener(lambda c, m: NOTICES.append(str(m).split(": ", 1)[-1]))
    R = lambda sid, title, sql, section, err=False: run(conn, sid, title, sql, section, err)  # noqa: E731

    # ── structure
    await R("S1", "Tables per schema", "SELECT table_schema, count(*) AS tables FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema','public') GROUP BY table_schema ORDER BY table_schema;", "structure")
    await R("S2", "Columns of administration.department", "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'administration' AND table_name = 'department' ORDER BY ordinal_position;", "structure")
    await R("S3", "Constraints of complaints.complaint", "SELECT conname AS constraint_name, CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS type FROM pg_constraint WHERE conrelid = 'complaints.complaint'::regclass AND contype IN ('p','f','u','c') ORDER BY contype, conname;", "structure")

    # ── sample data
    await R("D1", "Sample departments", "SELECT department_id, department_code, department_name, verification_status FROM administration.department ORDER BY department_id LIMIT 6;", "sample")
    await R("D2", "Sample schemes", "SELECT scheme_code, scheme_name, scheme_level, category, verification_status FROM schemes.scheme ORDER BY scheme_name LIMIT 6;", "sample")
    await R("D3", "Sample complaint categories", "SELECT category_id, category_code, category_name, default_priority, default_sla_hours FROM complaints.complaint_category ORDER BY category_id LIMIT 6;", "sample")

    # ── operations
    await R("Q1", "INNER JOIN: schemes with their department", "SELECT s.scheme_name, d.department_name, s.verification_status FROM schemes.scheme s JOIN administration.department d ON d.department_id = s.department_id ORDER BY s.scheme_name LIMIT 8;", "operations")
    await R("Q2", "Aggregate + GROUP BY: complaints per department", "SELECT d.department_name, count(*) AS total, count(*) FILTER (WHERE c.status IN ('resolved','closed')) AS resolved, round(100.0 * count(*) FILTER (WHERE c.status IN ('resolved','closed')) / count(*), 1) AS resolved_pct FROM complaints.complaint c JOIN administration.department d ON d.department_id = c.department_id GROUP BY d.department_name ORDER BY total DESC;", "operations")
    await R("Q3", "Subquery: departments with more complaints than the average department", "SELECT department_name FROM administration.department WHERE department_id IN (SELECT department_id FROM complaints.complaint GROUP BY department_id HAVING count(*) > (SELECT avg(n) FROM (SELECT count(*) AS n FROM complaints.complaint GROUP BY department_id) t)) ORDER BY department_name;", "operations")
    await R("Q4", "LEFT JOIN + COUNT: eligibility rules per scheme", "SELECT s.scheme_name, count(r.rule_id) AS rules FROM schemes.scheme s LEFT JOIN schemes.eligibility_rule r ON r.scheme_id = s.scheme_id GROUP BY s.scheme_name ORDER BY rules DESC, s.scheme_name LIMIT 6;", "operations")
    await R("Q5", "Pattern search (ILIKE) with ORDER BY", "SELECT service_name, category, processing_time FROM services.service WHERE service_name ILIKE '%certificate%' ORDER BY service_name;", "operations")
    await R("Q6", "Self-join: authority hierarchy", "SELECT a.authority_name, p.authority_name AS escalates_to FROM administration.authority a LEFT JOIN administration.authority p ON p.authority_id = a.parent_authority_id ORDER BY a.authority_id LIMIT 5;", "operations")

    # ── INSERT / UPDATE / DELETE
    await R("M1", "INSERT a department", "INSERT INTO administration.department (department_code, department_name, status) VALUES ('RPT-DEMO', 'Report Demonstration Department', 'active') RETURNING department_id, department_code, department_name;", "dml")
    await R("M2", "UPDATE it", "UPDATE administration.department SET department_name = 'Report Demo Department (renamed)', website_url = 'https://example.org' WHERE department_code = 'RPT-DEMO' RETURNING department_code, department_name, website_url;", "dml")
    await R("M3", "SELECT to confirm the change", "SELECT department_code, department_name, website_url FROM administration.department WHERE department_code = 'RPT-DEMO';", "dml")
    await R("M4", "DELETE it", "DELETE FROM administration.department WHERE department_code = 'RPT-DEMO';", "dml")
    await R("M5", "Confirm it is gone", "SELECT count(*) AS rows_left FROM administration.department WHERE department_code = 'RPT-DEMO';", "dml")

    # ── constraints
    await R("C1", "UNIQUE violation (duplicate department code)", "INSERT INTO administration.department (department_code, department_name) SELECT department_code, 'duplicate' FROM administration.department LIMIT 1;", "constraints", True)
    await R("C2", "CHECK violation (invalid scheme level)", "INSERT INTO schemes.scheme (scheme_code, scheme_name, scheme_level) VALUES ('X-1', 'Bad level', 'galactic');", "constraints", True)
    await R("C3", "FOREIGN KEY violation (unknown department)", "INSERT INTO schemes.scheme (scheme_code, scheme_name, scheme_level, department_id) VALUES ('X-2', 'Orphan scheme', 'state', 99999);", "constraints", True)
    await R("C4", "NOT NULL violation (missing name)", "INSERT INTO administration.department (department_code) VALUES ('X-3');", "constraints", True)
    await R("C5", "Governance CHECK: official_verified needs a source document", "UPDATE administration.department SET verification_status = 'official_verified' WHERE department_id = 1;", "constraints", True)

    # ── functions / procedure
    await R("F1", "Functions defined by the project", "SELECT n.nspname AS schema, p.proname AS function, pg_get_function_result(p.oid) AS returns FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname IN ('administration','complaints','schemes','system','audit') AND p.prokind = 'f' ORDER BY 1, 2;", "advanced")
    await R("F2", "Call the spatial function resolve_jurisdiction (NULLs: no boundary polygons are loaded in the demo database)", "SELECT * FROM administration.resolve_jurisdiction(80.2707, 13.0827);", "advanced")
    proc = """CREATE OR REPLACE PROCEDURE complaints.close_stale_resolved(p_days integer)
LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  UPDATE complaints.complaint SET status = 'closed'
  WHERE status = 'resolved' AND resolved_at < now() - make_interval(days => p_days);
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE '% resolved complaint(s) older than % days were closed', n, p_days;
  COMMIT;
END $$;"""
    await R("P1", "Create a stored procedure (illustrative; not used by the application)", proc, "advanced")
    await R("P2", "Complaints by status before the procedure", "SELECT status, count(*) FROM complaints.complaint WHERE status IN ('resolved','closed') GROUP BY status ORDER BY status;", "advanced")
    await R("P3", "CALL the procedure", "CALL complaints.close_stale_resolved(7);", "advanced")
    await R("P4", "Complaints by status after the procedure", "SELECT status, count(*) FROM complaints.complaint WHERE status IN ('resolved','closed') GROUP BY status ORDER BY status;", "advanced")

    # ── trigger
    ref = await conn.fetchval("SELECT complaint_ref FROM complaints.complaint WHERE status = 'classified' ORDER BY complaint_ref LIMIT 1")
    await R("T1", f"History of {ref} before the update", f"SELECT h.old_status, h.new_status, h.remarks FROM complaints.complaint_history h JOIN complaints.complaint c USING (complaint_id) WHERE c.complaint_ref = '{ref}' ORDER BY h.history_id;", "trigger")
    await R("T2", "UPDATE the status (the trigger trg_complaint_history fires)", f"UPDATE complaints.complaint SET status = 'assigned' WHERE complaint_ref = '{ref}' RETURNING complaint_ref, status;", "trigger")
    await R("T3", "History after the update: a new row was written by the trigger", f"SELECT h.old_status, h.new_status, h.remarks FROM complaints.complaint_history h JOIN complaints.complaint c USING (complaint_id) WHERE c.complaint_ref = '{ref}' ORDER BY h.history_id;", "trigger")
    await R("T4", "Write one audit row (INSERT is allowed)", "INSERT INTO audit.audit_log (action, entity_type, entity_id) VALUES ('report.demo', 'complaint', 'DEMO-0001') RETURNING audit_id, action, entity_type;", "trigger")
    await R("T5", "Append-only audit trail: the trigger blocks UPDATE", "UPDATE audit.audit_log SET action = 'tampered' WHERE action = 'report.demo';", "trigger", True)
    await R("T6", "...and DELETE", "DELETE FROM audit.audit_log WHERE action = 'report.demo';", "trigger", True)

    # ── views
    await R("V1", "View complaints.v_department_performance", "SELECT department_id, total, resolved, sla_breached FROM complaints.v_department_performance ORDER BY total DESC LIMIT 5;", "views")
    await R("V2", "View complaints.v_sla_breached (top 5 by lateness)", "SELECT complaint_ref, status, priority, date_trunc('hour', overdue_by) AS overdue_by FROM complaints.v_sla_breached ORDER BY overdue_by DESC LIMIT 5;", "views")
    await R("V3", "Definition of the view", "SELECT pg_get_viewdef('complaints.v_sla_breached'::regclass, true) AS definition;", "views")

    # ── transactions
    ref2 = await conn.fetchval("SELECT complaint_ref FROM complaints.complaint WHERE priority = 'medium' ORDER BY complaint_ref LIMIT 1")
    await R("X1", "BEGIN a transaction", "BEGIN;", "transactions")
    await R("X2", "UPDATE inside the transaction", f"UPDATE complaints.complaint SET priority = 'critical' WHERE complaint_ref = '{ref2}' RETURNING complaint_ref, priority;", "transactions")
    await R("X3", "ROLLBACK", "ROLLBACK;", "transactions")
    await R("X4", "After ROLLBACK the priority is unchanged", f"SELECT complaint_ref, priority FROM complaints.complaint WHERE complaint_ref = '{ref2}';", "transactions")
    await R("X5", "BEGIN, UPDATE, SAVEPOINT, second UPDATE", f"BEGIN; UPDATE complaints.complaint SET priority = 'high' WHERE complaint_ref = '{ref2}'; SAVEPOINT sp1; UPDATE complaints.complaint SET priority = 'low' WHERE complaint_ref = '{ref2}';", "transactions")
    await R("X6", "ROLLBACK TO SAVEPOINT then COMMIT", "ROLLBACK TO SAVEPOINT sp1; COMMIT;", "transactions")
    await R("X7", "After COMMIT only the first update persisted", f"SELECT complaint_ref, priority FROM complaints.complaint WHERE complaint_ref = '{ref2}';", "transactions")

    # ── indexes
    await R("I1", "Index methods beyond B-tree (GiST, GIN, HNSW)", "SELECT am.amname AS method, count(*) AS indexes FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid JOIN pg_am am ON am.oid = c.relam JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','public') GROUP BY am.amname ORDER BY am.amname;", "indexes")
    await R("I2", "Extensions installed", "SELECT extname, extversion FROM pg_extension ORDER BY extname;", "indexes")
    await R("I3", "Query plan for a join (EXPLAIN)", "EXPLAIN SELECT s.scheme_name, d.department_name FROM schemes.scheme s JOIN administration.department d ON d.department_id = s.department_id;", "indexes")
    await conn.close()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sql_evidence.json").write_text(json.dumps(EVIDENCE, indent=1, ensure_ascii=False), encoding="utf-8")
    script = ["-- MyGovt lab queries (PostgreSQL 16). Run on a SCRATCH database built with: python -m scripts.demo_env --db mygovt_dev_report --reset", ""]
    for e in EVIDENCE:
        script += [f"-- [{e['id']}] {e['title']}", e["sql"] if e["sql"].rstrip().endswith(";") else e["sql"] + ";", ""]
    (out / "lab_queries.sql").write_text("\n".join(script), encoding="utf-8")
    bad = [e["id"] for e in EVIDENCE if e["output"].endswith("<-- unexpected")]
    print(f"{len(EVIDENCE)} steps recorded; unexpected errors: {bad or 'none'}")


if __name__ == "__main__":
    asyncio.run(main())
