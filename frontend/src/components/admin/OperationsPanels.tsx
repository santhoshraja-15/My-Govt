"use client";

import { useCallback, useEffect, useState } from "react";
import { admin as adminAPI, complaints as complaintsAPI } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { assignmentText } from "@/lib/complaints";

const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString("en-IN") : "—");

/** Real complaints (synthetic test data excluded), with the legal next statuses for each row. */
export function ComplaintsPanel() {
  const { user } = useAuth();
  const canUpdate = user?.role === "state_admin";            // the status endpoint is open to officers / department / state admins
  const [filter, setFilter] = useState<"all" | "overdue" | "unassigned">("all");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    setData(null); setError("");
    adminAPI.complaints({ overdue: filter === "overdue" || undefined, unassigned: filter === "unassigned" || undefined, limit: 100 })
      .then(setData).catch((e) => setError(e.message || "Could not load complaints."));
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const move = async (id: string, status: string) => {
    setBusy(id);
    try { await complaintsAPI.updateStatus(id, status, "Updated from admin console"); load(); }
    catch (e: any) { setError(e.message || "Update failed."); }
    setBusy(null);
  };

  return (
    <div className="space-y-4" data-testid="complaints-panel">
      <div role="group" aria-label="Complaint filter" className="flex gap-2">
        {([["all", "All"], ["overdue", "SLA target missed"], ["unassigned", "No authority"]] as const).map(([k, label]) => (
          <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
            className={`px-3 py-1.5 rounded-full text-sm border ${filter === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>{label}</button>
        ))}
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <LoadingState />}
      {data && data.items.length === 0 && <EmptyState message="No complaints match this filter." />}
      {data && data.items.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="data-table text-xs">
            <thead><tr><th>Reference</th><th>Subject</th><th>Status</th><th>Department / routing</th><th>Target</th>{canUpdate && <th>Move to</th>}</tr></thead>
            <tbody>
              {data.items.map((c: any) => (
                <tr key={c.complaint_id} data-testid="complaint-row">
                  <td className="font-mono whitespace-nowrap">{c.reference_number}</td>
                  <td className="max-w-xs truncate">{c.title}</td>
                  <td><span className="badge badge-slate" data-status={c.status}>{c.status}</span></td>
                  <td className="max-w-xs">{assignmentText(c.assignment_state, c.department_name, c.authority_name)}</td>
                  <td className={c.sla_breached ? "text-red-700 font-semibold" : ""}>{fmt(c.due_date)}{c.sla_breached ? " (missed)" : ""}</td>
                  {canUpdate && (
                    <td>
                      {c.allowed_next.length === 0 ? <span className="text-slate-400">final</span> : (
                        <select aria-label={`Move ${c.reference_number}`} disabled={busy === c.complaint_id} defaultValue=""
                          onChange={(e) => e.target.value && move(c.complaint_id, e.target.value)} className="input py-1 text-xs">
                          <option value="">—</option>
                          {c.allowed_next.map((s: string) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500 p-3">{data.total} complaint(s) in total. Only legal transitions are offered.</p>
        </div>
      )}
    </div>
  );
}

export function DepartmentPerformancePanel() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setRows(null); setError("");
    adminAPI.departmentPerformance().then(setRows).catch((e) => setError(e.message || "Could not load."));
  }, []);
  useEffect(() => { load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return <LoadingState />;
  if (rows.length === 0) return <EmptyState message="No complaints have been routed to a department yet." />;
  return (
    <div className="card overflow-x-auto" data-testid="department-performance">
      <table className="data-table text-xs">
        <thead><tr><th>Department</th><th>Complaints</th><th>Resolved</th><th>SLA target missed</th><th>No authority</th><th>Avg resolution (h)</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.department_id}>
              <td>{r.department_name}</td><td>{r.total}</td><td>{r.resolved}</td>
              <td className={r.sla_breached ? "text-red-700 font-semibold" : ""}>{r.sla_breached}</td>
              <td>{r.without_authority}</td><td>{r.avg_resolution_hours ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Records that still need an official source. The "asserted reference" is what the curated dataset claims; it is NOT confirmed. */
export function VerificationQueuePanel() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("scheme");
  const load = useCallback(() => {
    setData(null); setError("");
    adminAPI.verificationQueue().then(setData).catch((e) => setError(e.message || "Could not load."));
  }, []);
  useEffect(() => { load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <LoadingState />;
  const items = data.queue.filter((i: any) => i.kind === kind);
  return (
    <div className="space-y-4" data-testid="verification-queue">
      <p className="text-sm text-slate-600">
        {data.queue.length} records are not <b>official_verified</b>. A reference shown here is asserted by the curated dataset and has
        <b> not</b> been confirmed against the issuing document. Promotion requires a recorded evidence reference and a logged reason.
      </p>
      <div role="group" aria-label="Record type" className="flex gap-2">
        {["scheme", "service", "department", "district"].map((k) => (
          <button key={k} onClick={() => setKind(k)} aria-pressed={kind === k}
            className={`px-3 py-1.5 rounded-full text-sm border capitalize ${kind === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>
            {k} ({data.queue.filter((i: any) => i.kind === k).length})
          </button>
        ))}
      </div>
      <div className="card overflow-x-auto">
        <table className="data-table text-xs">
          <thead><tr><th>Code</th><th>Name</th><th>Status</th><th>Asserted reference (unconfirmed)</th></tr></thead>
          <tbody>
            {items.map((i: any) => (
              <tr key={i.code} data-testid="queue-row"><td className="font-mono">{i.code}</td><td>{i.name}</td>
                <td><VerificationBadge status={i.verification_status} /></td><td>{i.source_document_ref || "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Recent status changes</p>
        <ul className="text-xs space-y-1">
          {data.recent_changes.map((c: any, idx: number) => (
            <li key={idx}>{c.table_name} · {c.record_key}: {c.old_status ?? "—"} → <b>{c.new_status}</b> <span className="text-slate-500">({c.reason})</span></li>
          ))}
        </ul>
      </div>
    </div>
  );
}
