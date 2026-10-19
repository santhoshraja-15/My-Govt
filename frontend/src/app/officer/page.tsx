"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Building2, CheckCircle2, ClipboardList, Hourglass, UserCheck, UserX, X } from "lucide-react";
import { complaints as complaintsAPI } from "@/lib/api";
import { useGuard } from "@/lib/useGuard";
import { BarList, DonutChart, StatCard } from "@/components/ui/charts";
import { StatusBadge, STATUS_META } from "@/components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useToast } from "@/components/ui/Toast";
import { assignmentText } from "@/lib/complaints";

const STAFF = ["officer", "department_admin", "state_admin", "system_admin"];
const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");
const PRIORITY: Record<string, string> = { critical: "badge-red", high: "badge-yellow", medium: "badge-blue", low: "badge-slate" };

type Filter = "all" | "mine" | "unassigned";

function Detail({ id, listItem, role, officers, onClose, onChanged }: {
  id: string; listItem: any; role: string; officers: any[]; onClose: () => void; onChanged: () => void;
}) {
  const { notify } = useToast();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [remarks, setRemarks] = useState("");
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const canPickOfficer = role !== "officer";

  const load = useCallback(() => {
    setD(null); setError("");
    complaintsAPI.get(id).then(setD).catch((e) => setError(e.message || "Could not load the complaint."));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true);
    try { await fn(); notify("success", ok); setRemarks(""); onChanged(); load(); }
    catch (e: any) { notify("error", e.message || "The action failed."); }
    setBusy(false);
  };

  return (
    <aside className="card p-5 space-y-4 lg:sticky lg:top-4 animate-slide-up" aria-label="Complaint detail" data-testid="complaint-detail">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-xs text-slate-500">{listItem.reference_number}</p>
          <h2 className="font-bold text-slate-900">{listItem.title}</h2>
        </div>
        <button onClick={onClose} className="btn-ghost p-1.5" aria-label="Close detail"><X size={16} /></button>
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !d && <LoadingState />}
      {d && (
        <>
          <div className="flex flex-wrap gap-2 items-center">
            <StatusBadge status={d.status} />
            {d.priority && <span className={`badge ${PRIORITY[d.priority] ?? "badge-slate"}`}>{d.priority} priority</span>}
            {listItem.is_synthetic && <span className="badge badge-purple" data-testid="demo-badge" title="Synthetic demonstration record">DEMO DATA</span>}
          </div>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{d.description}</p>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div><dt className="text-slate-500">Category</dt><dd className="font-medium">{d.category_name ?? "—"}</dd></div>
            <div><dt className="text-slate-500">Target date</dt><dd className="font-medium">{fmt(d.due_date)}</dd></div>
            <div><dt className="text-slate-500">Assigned officer</dt><dd className="font-medium" data-testid="detail-officer">{d.officer_name ?? "Not assigned"}</dd></div>
            <div><dt className="text-slate-500">Department</dt><dd className="font-medium">{d.department_name ?? "—"}</dd></div>
          </dl>
          <p className="text-xs text-slate-500">{assignmentText(d.assignment_state, d.department_name, d.authority_name)}</p>

          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">History</p>
            <ol className="space-y-2 border-l-2 border-slate-100 pl-4" data-testid="timeline">
              {d.timeline.map((h: any, i: number) => (
                <li key={i} className="text-xs relative">
                  <span className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-brand-500" aria-hidden />
                  <span className="font-semibold">{STATUS_META[h.new_status]?.label ?? h.new_status}</span>
                  <span className="text-slate-500"> · {fmt(h.changed_at)}</span>
                  {h.remarks && <p className="text-slate-600">{h.remarks}</p>}
                </li>
              ))}
            </ol>
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Actions</p>
            {canPickOfficer ? (
              <div className="flex gap-2">
                <select aria-label="Officer to assign" className="input py-1.5 text-sm" value={pick} onChange={(e) => setPick(e.target.value)}>
                  <option value="">Choose officer…</option>
                  {officers.map((o) => <option key={o.officer_id} value={o.officer_id}>{o.name} ({o.open_complaints} open)</option>)}
                </select>
                <button disabled={!pick || busy} className="btn-secondary shrink-0" data-testid="assign-btn"
                  onClick={() => act(() => complaintsAPI.assign(id, pick, remarks || undefined), "Complaint assigned.")}>
                  <UserCheck size={14} /> Assign
                </button>
              </div>
            ) : (
              <button disabled={busy} className="btn-secondary" data-testid="assign-me-btn"
                onClick={() => act(() => complaintsAPI.assign(id, undefined, remarks || undefined), "Assigned to you.")}>
                <UserCheck size={14} /> Assign to me
              </button>
            )}
            <label className="label" htmlFor="remarks">Remarks (shown to the citizen in the history)</label>
            <textarea id="remarks" className="input" rows={2} maxLength={500} value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="e.g. Crew dispatched; expected completion in 2 days" />
            {listItem.allowed_next.length === 0 ? (
              <p className="text-xs text-slate-500">This complaint is in a final state; no further changes are allowed.</p>
            ) : (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Move to status">
                {listItem.allowed_next.map((s: string) => (
                  <button key={s} disabled={busy} data-testid={`move-${s}`} className="btn-primary"
                    onClick={() => act(() => complaintsAPI.updateStatus(id, s, remarks || undefined), `Status changed to ${STATUS_META[s]?.label ?? s}.`)}>
                    {STATUS_META[s]?.label ?? s}
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  );
}

export default function OfficerPage() {
  const user = useGuard((r) => STAFF.includes(r));
  const [filter, setFilter] = useState<Filter>("all");
  const [status, setStatus] = useState("");
  const [data, setData] = useState<any>(null);
  const [officers, setOfficers] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(() => {
    setError("");
    complaintsAPI.staffList({ status: status || undefined, mine: filter === "mine", unassigned: filter === "unassigned", limit: 100 })
      .then(setData).catch((e) => setError(e.message || "Could not load complaints."));
  }, [filter, status]);
  useEffect(() => { if (user) load(); }, [user, load]);
  useEffect(() => { if (user && user.role !== "officer") complaintsAPI.officers().then(setOfficers).catch(() => setOfficers([])); }, [user]);

  if (!user) return <LoadingState />;
  const counts: Record<string, number> = data?.status_counts ?? {};
  const open = Object.entries(counts).filter(([s]) => !["resolved", "closed", "rejected"].includes(s)).reduce((a, [, v]) => a + v, 0);
  const slices = Object.entries(counts).map(([s, v]) => ({ label: STATUS_META[s]?.label ?? s, value: v, color: STATUS_META[s]?.hex ?? "#94a3b8" }));
  const sel = data?.items.find((c: any) => c.complaint_id === selected);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6" data-testid="officer-console">
      <header>
        <p className="text-sm text-slate-500 flex items-center gap-1"><Building2 size={14} /> Officer console</p>
        <h1 className="text-2xl font-black text-slate-900" data-testid="officer-scope">
          {data ? (data.department_name ?? "All departments") : "Loading…"}
        </h1>
        <p className="text-sm text-slate-500">You can see and act on complaints of {data?.department_scope ? "your department" : "every department"} only.</p>
        {data?.demo_data_included && (
          <p className="mt-2 inline-flex rounded-lg bg-purple-50 border border-purple-200 px-3 py-1.5 text-xs text-purple-800" data-testid="demo-banner">
            Demonstration mode: the list includes clearly labelled synthetic complaints.
          </p>
        )}
      </header>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <LoadingState />}

      {data && (
        <>
          <section aria-label="Summary" className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard testId="o-open" label="Open complaints" value={open} icon={<Hourglass size={18} />} />
            <StatCard testId="o-overdue" label="Past target" value={data.overdue} tone={data.overdue ? "red" : "slate"} icon={<AlertTriangle size={18} />} />
            <StatCard testId="o-unassigned" label="Not assigned" value={data.unassigned} tone="amber" icon={<UserX size={18} />} />
            <StatCard testId="o-resolved" label="Resolved / closed" value={(counts.resolved ?? 0) + (counts.closed ?? 0)} tone="green" icon={<CheckCircle2 size={18} />} />
          </section>

          <section className="card p-5 min-w-0" aria-labelledby="mix-h">
            <h2 id="mix-h" className="font-bold text-slate-900 mb-4">By status</h2>
            {slices.length ? (
              <div className="grid md:grid-cols-2 gap-8 items-center">
                <DonutChart slices={slices} centerLabel="complaints" testId="officer-donut" />
                <BarList bars={slices.map((s) => ({ label: s.label, value: s.value, color: s.color }))} />
              </div>
            ) : <EmptyState message="No complaints." />}
          </section>

          <div>
            <section className="space-y-4 min-w-0" aria-labelledby="list-h">
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="list-h" className="font-bold text-slate-900 mr-2 flex items-center gap-2"><ClipboardList size={18} /> Complaints</h2>
                <div role="group" aria-label="Assignment filter" className="flex gap-2">
                  {([["all", "All"], ["mine", "Assigned to me"], ["unassigned", "Not assigned"]] as const).map(([k, label]) => (
                    <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)} data-testid={`filter-${k}`}
                      className={`px-3 py-1.5 rounded-full text-sm border ${filter === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>{label}</button>
                  ))}
                </div>
                <select aria-label="Filter by status" className="input w-auto py-1.5 text-sm ml-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">Any status</option>
                  {Object.keys(STATUS_META).map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
                </select>
              </div>

              <div className={`grid gap-6 ${sel ? "xl:grid-cols-5" : ""}`}>
                <div className={`card overflow-x-auto min-w-0 ${sel ? "xl:col-span-3" : ""}`}>
                  {data.items.length === 0 ? <EmptyState message="No complaints match this filter." /> : (
                    <table className="data-table text-xs">
                      <thead><tr><th>Reference</th><th>Subject</th><th>Priority</th><th>Status</th><th>Officer</th><th>Target</th></tr></thead>
                      <tbody>
                        {data.items.map((c: any) => (
                          <tr key={c.complaint_id} data-testid="staff-row" onClick={() => setSelected(c.complaint_id)}
                            className={`cursor-pointer ${selected === c.complaint_id ? "bg-brand-50" : ""}`}>
                            <td className="font-mono whitespace-nowrap">
                              <button className="underline text-brand-700" onClick={(e) => { e.stopPropagation(); setSelected(c.complaint_id); }}>{c.reference_number}</button>
                            </td>
                            <td className="max-w-[16rem] truncate">{c.title}</td>
                            <td><span className={`badge ${PRIORITY[c.priority] ?? "badge-slate"}`}>{c.priority}</span></td>
                            <td><StatusBadge status={c.status} /></td>
                            <td>{c.officer_name ?? <span className="text-slate-500">—</span>}</td>
                            <td className={c.sla_breached ? "text-red-700 font-semibold whitespace-nowrap" : "whitespace-nowrap"}>{fmt(c.due_date)}{c.sla_breached ? " (past)" : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <p className="text-xs text-slate-500 p-3">{data.total} complaint(s). Priority order: past target first, then priority, then newest.</p>
                </div>
                {sel && <div className="xl:col-span-2 min-w-0"><Detail key={sel.complaint_id} id={sel.complaint_id} listItem={sel} role={user.role} officers={officers}
                  onClose={() => setSelected(null)} onChanged={load} /></div>}
              </div>
            </section>
          </div>
        </>
      )}
    </main>
  );
}
