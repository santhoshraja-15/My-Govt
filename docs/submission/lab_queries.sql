-- MyGovt lab queries (PostgreSQL 16). Run on a SCRATCH database built with: python -m scripts.demo_env --db mygovt_dev_report --reset

-- [S1] Tables per schema
SELECT table_schema, count(*) AS tables FROM information_schema.tables WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema','public') GROUP BY table_schema ORDER BY table_schema;

-- [S2] Columns of administration.department
SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = 'administration' AND table_name = 'department' ORDER BY ordinal_position;

-- [S3] Constraints of complaints.complaint
SELECT conname AS constraint_name, CASE contype WHEN 'p' THEN 'PRIMARY KEY' WHEN 'f' THEN 'FOREIGN KEY' WHEN 'u' THEN 'UNIQUE' WHEN 'c' THEN 'CHECK' END AS type FROM pg_constraint WHERE conrelid = 'complaints.complaint'::regclass AND contype IN ('p','f','u','c') ORDER BY contype, conname;

-- [D1] Sample departments
SELECT department_id, department_code, department_name, verification_status FROM administration.department ORDER BY department_id LIMIT 6;

-- [D2] Sample schemes
SELECT scheme_code, scheme_name, scheme_level, category, verification_status FROM schemes.scheme ORDER BY scheme_name LIMIT 6;

-- [D3] Sample complaint categories
SELECT category_id, category_code, category_name, default_priority, default_sla_hours FROM complaints.complaint_category ORDER BY category_id LIMIT 6;

-- [Q1] INNER JOIN: schemes with their department
SELECT s.scheme_name, d.department_name, s.verification_status FROM schemes.scheme s JOIN administration.department d ON d.department_id = s.department_id ORDER BY s.scheme_name LIMIT 8;

-- [Q2] Aggregate + GROUP BY: complaints per department
SELECT d.department_name, count(*) AS total, count(*) FILTER (WHERE c.status IN ('resolved','closed')) AS resolved, round(100.0 * count(*) FILTER (WHERE c.status IN ('resolved','closed')) / count(*), 1) AS resolved_pct FROM complaints.complaint c JOIN administration.department d ON d.department_id = c.department_id GROUP BY d.department_name ORDER BY total DESC;

-- [Q3] Subquery: departments with more complaints than the average department
SELECT department_name FROM administration.department WHERE department_id IN (SELECT department_id FROM complaints.complaint GROUP BY department_id HAVING count(*) > (SELECT avg(n) FROM (SELECT count(*) AS n FROM complaints.complaint GROUP BY department_id) t)) ORDER BY department_name;

-- [Q4] LEFT JOIN + COUNT: eligibility rules per scheme
SELECT s.scheme_name, count(r.rule_id) AS rules FROM schemes.scheme s LEFT JOIN schemes.eligibility_rule r ON r.scheme_id = s.scheme_id GROUP BY s.scheme_name ORDER BY rules DESC, s.scheme_name LIMIT 6;

-- [Q5] Pattern search (ILIKE) with ORDER BY
SELECT service_name, category, processing_time FROM services.service WHERE service_name ILIKE '%certificate%' ORDER BY service_name;

-- [Q6] Self-join: authority hierarchy
SELECT a.authority_name, p.authority_name AS escalates_to FROM administration.authority a LEFT JOIN administration.authority p ON p.authority_id = a.parent_authority_id ORDER BY a.authority_id LIMIT 5;

-- [M1] INSERT a department
INSERT INTO administration.department (department_code, department_name, status) VALUES ('RPT-DEMO', 'Report Demonstration Department', 'active') RETURNING department_id, department_code, department_name;

-- [M2] UPDATE it
UPDATE administration.department SET department_name = 'Report Demo Department (renamed)', website_url = 'https://example.org' WHERE department_code = 'RPT-DEMO' RETURNING department_code, department_name, website_url;

-- [M3] SELECT to confirm the change
SELECT department_code, department_name, website_url FROM administration.department WHERE department_code = 'RPT-DEMO';

-- [M4] DELETE it
DELETE FROM administration.department WHERE department_code = 'RPT-DEMO';

-- [M5] Confirm it is gone
SELECT count(*) AS rows_left FROM administration.department WHERE department_code = 'RPT-DEMO';

-- [C1] UNIQUE violation (duplicate department code)
INSERT INTO administration.department (department_code, department_name) SELECT department_code, 'duplicate' FROM administration.department LIMIT 1;

-- [C2] CHECK violation (invalid scheme level)
INSERT INTO schemes.scheme (scheme_code, scheme_name, scheme_level) VALUES ('X-1', 'Bad level', 'galactic');

-- [C3] FOREIGN KEY violation (unknown department)
INSERT INTO schemes.scheme (scheme_code, scheme_name, scheme_level, department_id) VALUES ('X-2', 'Orphan scheme', 'state', 99999);

-- [C4] NOT NULL violation (missing name)
INSERT INTO administration.department (department_code) VALUES ('X-3');

-- [C5] Governance CHECK: official_verified needs a source document
UPDATE administration.department SET verification_status = 'official_verified' WHERE department_id = 1;

-- [F1] Functions defined by the project
SELECT n.nspname AS schema, p.proname AS function, pg_get_function_result(p.oid) AS returns FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname IN ('administration','complaints','schemes','system','audit') AND p.prokind = 'f' ORDER BY 1, 2;

-- [F2] Call the spatial function resolve_jurisdiction (NULLs: no boundary polygons are loaded in the demo database)
SELECT * FROM administration.resolve_jurisdiction(80.2707, 13.0827);

-- [P1] Create a stored procedure (illustrative; not used by the application)
CREATE OR REPLACE PROCEDURE complaints.close_stale_resolved(p_days integer)
LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  UPDATE complaints.complaint SET status = 'closed'
  WHERE status = 'resolved' AND resolved_at < now() - make_interval(days => p_days);
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE '% resolved complaint(s) older than % days were closed', n, p_days;
  COMMIT;
END $$;

-- [P2] Complaints by status before the procedure
SELECT status, count(*) FROM complaints.complaint WHERE status IN ('resolved','closed') GROUP BY status ORDER BY status;

-- [P3] CALL the procedure
CALL complaints.close_stale_resolved(7);

-- [P4] Complaints by status after the procedure
SELECT status, count(*) FROM complaints.complaint WHERE status IN ('resolved','closed') GROUP BY status ORDER BY status;

-- [T1] History of SYN-7-000019 before the update
SELECT h.old_status, h.new_status, h.remarks FROM complaints.complaint_history h JOIN complaints.complaint c USING (complaint_id) WHERE c.complaint_ref = 'SYN-7-000019' ORDER BY h.history_id;

-- [T2] UPDATE the status (the trigger trg_complaint_history fires)
UPDATE complaints.complaint SET status = 'assigned' WHERE complaint_ref = 'SYN-7-000019' RETURNING complaint_ref, status;

-- [T3] History after the update: a new row was written by the trigger
SELECT h.old_status, h.new_status, h.remarks FROM complaints.complaint_history h JOIN complaints.complaint c USING (complaint_id) WHERE c.complaint_ref = 'SYN-7-000019' ORDER BY h.history_id;

-- [T4] Write one audit row (INSERT is allowed)
INSERT INTO audit.audit_log (action, entity_type, entity_id) VALUES ('report.demo', 'complaint', 'DEMO-0001') RETURNING audit_id, action, entity_type;

-- [T5] Append-only audit trail: the trigger blocks UPDATE
UPDATE audit.audit_log SET action = 'tampered' WHERE action = 'report.demo';

-- [T6] ...and DELETE
DELETE FROM audit.audit_log WHERE action = 'report.demo';

-- [V1] View complaints.v_department_performance
SELECT department_id, total, resolved, sla_breached FROM complaints.v_department_performance ORDER BY total DESC LIMIT 5;

-- [V2] View complaints.v_sla_breached (top 5 by lateness)
SELECT complaint_ref, status, priority, date_trunc('hour', overdue_by) AS overdue_by FROM complaints.v_sla_breached ORDER BY overdue_by DESC LIMIT 5;

-- [V3] Definition of the view
SELECT pg_get_viewdef('complaints.v_sla_breached'::regclass, true) AS definition;

-- [X1] BEGIN a transaction
BEGIN;

-- [X2] UPDATE inside the transaction
UPDATE complaints.complaint SET priority = 'critical' WHERE complaint_ref = 'DEMO-0003' RETURNING complaint_ref, priority;

-- [X3] ROLLBACK
ROLLBACK;

-- [X4] After ROLLBACK the priority is unchanged
SELECT complaint_ref, priority FROM complaints.complaint WHERE complaint_ref = 'DEMO-0003';

-- [X5] BEGIN, UPDATE, SAVEPOINT, second UPDATE
BEGIN; UPDATE complaints.complaint SET priority = 'high' WHERE complaint_ref = 'DEMO-0003'; SAVEPOINT sp1; UPDATE complaints.complaint SET priority = 'low' WHERE complaint_ref = 'DEMO-0003';

-- [X6] ROLLBACK TO SAVEPOINT then COMMIT
ROLLBACK TO SAVEPOINT sp1; COMMIT;

-- [X7] After COMMIT only the first update persisted
SELECT complaint_ref, priority FROM complaints.complaint WHERE complaint_ref = 'DEMO-0003';

-- [I1] Index methods beyond B-tree (GiST, GIN, HNSW)
SELECT am.amname AS method, count(*) AS indexes FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid JOIN pg_am am ON am.oid = c.relam JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','public') GROUP BY am.amname ORDER BY am.amname;

-- [I2] Extensions installed
SELECT extname, extversion FROM pg_extension ORDER BY extname;

-- [I3] Query plan for a join (EXPLAIN)
EXPLAIN SELECT s.scheme_name, d.department_name FROM schemes.scheme s JOIN administration.department d ON d.department_id = s.department_id;
