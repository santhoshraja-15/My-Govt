"use client";

import { useCallback, useEffect, useState } from "react";
import { admin as adminAPI, complaints as complaintsAPI } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { assignmentTextT } from "@/lib/complaints";
import { useLang, type TKey } from "@/lib/i18n";
import { STATUS_META } from "@/components/ui/StatusBadge";

function useFmt() {
  const { lang } = useLang();
  return (d?: string | null) => (d ? new Date(d).toLocaleString(lang === "ta" ? "ta-IN" : "en-IN") : "—");
}
function useStatusLabel() {
  const { t } = useLang();
  return (s: string) => (STATUS_META[s]?.key ? t(STATUS_META[s].key as TKey) : s);
}

/** Real complaints (synthetic test data excluded), with the legal next statuses for each row. */
export function ComplaintsPanel() {
  const { user } = useAuth();
  const { t, apiError, dept } = useLang();
  const fmt = useFmt();
  const statusLabel = useStatusLabel();
  const canUpdate = user?.role === "state_admin";            // the status endpoint is open to officers / department / state admins
  const [filter, setFilter] = useState<"all" | "overdue" | "unassigned">("all");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    setData(null); setError("");
    adminAPI.complaints({ overdue: filter === "overdue" || undefined, unassigned: filter === "unassigned" || undefined, limit: 100 })
      .then(setData).catch((e) => setError(apiError(e)));
  }, [filter, apiError]);
  useEffect(() => { load(); }, [load]);

  const move = async (id: string, status: string) => {
    setBusy(id);
    try { await complaintsAPI.updateStatus(id, status, t("ad.op.adminNote")); load(); }
    catch (e: any) { setError(apiError(e)); }
    setBusy(null);
  };

  return (
    <div className="space-y-4" data-testid="complaints-panel">
      <div role="group" aria-label={t("ad.op.filterGroup")} className="flex gap-2">
        {([["all", "ad.op.f.all"], ["overdue", "ad.op.f.overdue"], ["unassigned", "ad.op.f.unassigned"]] as const).map(([k, lk]) => (
          <button key={k} onClick={() => setFilter(k)} aria-pressed={filter === k}
            className={`px-3 py-1.5 rounded-full text-sm border ${filter === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>{t(lk)}</button>
        ))}
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <LoadingState />}
      {data && data.items.length === 0 && <EmptyState message={t("ad.op.noMatch")} />}
      {data && data.items.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="data-table text-xs">
            <thead><tr><th>{t("ad.op.col.ref")}</th><th>{t("ad.op.col.subject")}</th><th>{t("ad.op.col.status")}</th><th>{t("ad.op.col.routing")}</th><th>{t("ad.op.col.target")}</th>{canUpdate && <th>{t("ad.op.col.move")}</th>}</tr></thead>
            <tbody>
              {data.items.map((c: any) => (
                <tr key={c.complaint_id} data-testid="complaint-row">
                  <td className="font-mono whitespace-nowrap">{c.reference_number}</td>
                  <td className="max-w-xs truncate" lang="en">{c.title}</td>
                  <td><span className="badge badge-slate" data-status={c.status}>{statusLabel(c.status)}</span></td>
                  <td className="max-w-xs">{assignmentTextT(t, c.assignment_state, c.department_name, c.authority_name, dept)}</td>
                  <td className={c.sla_breached ? "text-red-700 font-semibold" : ""}>{fmt(c.due_date)}{c.sla_breached ? ` ${t("ad.op.missed")}` : ""}</td>
                  {canUpdate && (
                    <td>
                      {c.allowed_next.length === 0 ? <span className="text-slate-500">{t("ad.op.final")}</span> : (
                        <select aria-label={t("ad.op.move", { ref: c.reference_number })} disabled={busy === c.complaint_id} defaultValue=""
                          onChange={(e) => e.target.value && move(c.complaint_id, e.target.value)} className="input py-1 text-xs">
                          <option value="">—</option>
                          {c.allowed_next.map((s: string) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                        </select>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500 p-3">{t("ad.op.total", { n: data.total })}</p>
        </div>
      )}
    </div>
  );
}

export function DepartmentPerformancePanel() {
  const { t, apiError, dept } = useLang();
  const [rows, setRows] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setRows(null); setError("");
    adminAPI.departmentPerformance().then(setRows).catch((e) => setError(apiError(e)));
  }, [apiError]);
  useEffect(() => { load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return <LoadingState />;
  if (rows.length === 0) return <EmptyState message={t("ad.dp.none")} />;
  return (
    <div className="card overflow-x-auto" data-testid="department-performance">
      <table className="data-table text-xs">
        <thead><tr><th>{t("ad.dp.col.dept")}</th><th>{t("ad.dp.col.total")}</th><th>{t("ad.dp.col.resolved")}</th><th>{t("ad.dp.col.sla")}</th><th>{t("ad.dp.col.noAuth")}</th><th>{t("ad.dp.col.avg")}</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.department_id}>
              <td>{dept(r.department_name)}</td><td>{r.total}</td><td>{r.resolved}</td>
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
  const { t, label, apiError, names } = useLang();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [kind, setKind] = useState("scheme");
  const load = useCallback(() => {
    setData(null); setError("");
    adminAPI.verificationQueue().then(setData).catch((e) => setError(apiError(e)));
  }, [apiError]);
  useEffect(() => { load(); }, [load]);
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!data) return <LoadingState />;
  const items = data.queue.filter((i: any) => i.kind === kind);
  return (
    <div className="space-y-4" data-testid="verification-queue">
      <p className="text-sm text-slate-600">
        {t("ad.vq.intro", { n: data.queue.length })}
      </p>
      <div role="group" aria-label={t("ad.vq.recordType")} className="flex gap-2">
        {["scheme", "service", "department", "district"].map((k) => (
          <button key={k} onClick={() => setKind(k)} aria-pressed={kind === k}
            className={`px-3 py-1.5 rounded-full text-sm border ${kind === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>
            {label("ad.vq.kind", k)} ({data.queue.filter((i: any) => i.kind === k).length})
          </button>
        ))}
      </div>
      <div className="card overflow-x-auto">
        <table className="data-table text-xs">
          <thead><tr><th>{t("ad.vq.col.code")}</th><th>{t("ad.vq.col.name")}</th><th>{t("ad.vq.col.status")}</th><th>{t("ad.vq.col.ref")}</th></tr></thead>
          <tbody>
            {items.map((i: any) => (
              <tr key={i.code} data-testid="queue-row"><td className="font-mono">{i.code}</td><td>{names(i.name, i.name_ta).primary}{names(i.name, i.name_ta).secondary && <span className="block text-slate-500" data-i18n-skip>{names(i.name, i.name_ta).secondary}</span>}</td>
                <td><VerificationBadge status={i.verification_status} /></td><td lang="en">{i.source_document_ref || "—"}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card p-4">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{t("ad.vq.recent")}</p>
        <ul className="text-xs space-y-1">
          {data.recent_changes.map((c: any, idx: number) => (
            <li key={idx}><span className="font-mono">{c.table_name} · {c.record_key}</span>: {c.old_status ? label("vs", c.old_status) : "—"} → <b>{label("vs", c.new_status)}</b> <span className="text-slate-500" lang="en">({c.reason})</span></li>
          ))}
        </ul>
      </div>
    </div>
  );
}
