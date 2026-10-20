"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Building2, CheckCircle2, ClipboardList, Hourglass, UserCheck, UserX, X } from "lucide-react";
import { complaints as complaintsAPI } from "@/lib/api";
import { useGuard } from "@/lib/useGuard";
import { BarList, DonutChart, StatCard } from "@/components/ui/charts";
import { StatusBadge, STATUS_META } from "@/components/ui/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useToast } from "@/components/ui/Toast";
import { assignmentTextT } from "@/lib/complaints";
import { useLang, type TKey } from "@/lib/i18n";

const STAFF = ["officer", "department_admin", "state_admin", "system_admin"];
function useFmt() {
  const { lang } = useLang();
  return (d?: string | null) => (d ? new Date(d).toLocaleString(lang === "ta" ? "ta-IN" : "en-IN", { dateStyle: "medium", timeStyle: "short" }) : "—");
}
function useStatusLabel() {
  const { t } = useLang();
  return (s: string) => (STATUS_META[s]?.key ? t(STATUS_META[s].key as TKey) : s);
}
const PRIORITY: Record<string, string> = { critical: "badge-red", high: "badge-yellow", medium: "badge-blue", low: "badge-slate" };

type Filter = "all" | "mine" | "unassigned";

function Detail({ id, listItem, role, officers, onClose, onChanged }: {
  id: string; listItem: any; role: string; officers: any[]; onClose: () => void; onChanged: () => void;
}) {
  const { notify } = useToast();
  const { t, label, apiError, dept, cat } = useLang();
  const fmt = useFmt();
  const statusLabel = useStatusLabel();
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const [remarks, setRemarks] = useState("");
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const canPickOfficer = role !== "officer";

  const load = useCallback(() => {
    setD(null); setError("");
    complaintsAPI.get(id).then(setD).catch((e) => setError(apiError(e)));
  }, [id, apiError]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    setBusy(true);
    try { await fn(); notify("success", ok); setRemarks(""); onChanged(); load(); }
    catch (e: any) { notify("error", apiError(e)); }
    setBusy(false);
  };

  return (
    <aside className="card p-5 space-y-4 lg:sticky lg:top-4 animate-slide-up" aria-label={t("of.d.aria")} data-testid="complaint-detail">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-xs text-slate-500">{listItem.reference_number}</p>
          <h2 className="font-bold text-slate-900" lang="en">{listItem.title}</h2>
        </div>
        <button onClick={onClose} className="btn-ghost p-1.5" aria-label={t("of.d.close")}><X size={16} /></button>
      </div>
      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !d && <LoadingState />}
      {d && (
        <>
          <div className="flex flex-wrap gap-2 items-center">
            <StatusBadge status={d.status} />
            {d.priority && <span className={`badge ${PRIORITY[d.priority] ?? "badge-slate"}`}>{t("of.d.priority", { priority: label("priority", d.priority) })}</span>}
            {listItem.is_synthetic && <span className="badge badge-purple" data-testid="demo-badge" title={t("of.d.demoTitle")}>{t("of.d.demoBadge")}</span>}
          </div>
          <p className="text-sm text-slate-700 whitespace-pre-wrap" lang="en">{d.description}</p>
          <dl className="grid grid-cols-2 gap-3 text-xs">
            <div><dt className="text-slate-500">{t("of.d.category")}</dt><dd className="font-medium">{d.category_name ? cat(d.category_name) : "—"}</dd></div>
            <div><dt className="text-slate-500">{t("of.d.target")}</dt><dd className="font-medium">{fmt(d.due_date)}</dd></div>
            <div><dt className="text-slate-500">{t("of.d.officer")}</dt><dd className="font-medium" data-testid="detail-officer" lang="en">{d.officer_name ?? t("of.d.notAssigned")}</dd></div>
            <div><dt className="text-slate-500">{t("of.d.department")}</dt><dd className="font-medium">{d.department_name ? dept(d.department_name) : "—"}</dd></div>
          </dl>
          <p className="text-xs text-slate-500">{assignmentTextT(t, d.assignment_state, d.department_name, d.authority_name, dept)}</p>

          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">{t("of.d.history")}</p>
            <ol className="space-y-2 border-l-2 border-slate-100 pl-4" data-testid="timeline">
              {d.timeline.map((h: any, i: number) => (
                <li key={i} className="text-xs relative">
                  <span className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-brand-500" aria-hidden />
                  <span className="font-semibold">{statusLabel(h.new_status)}</span>
                  <span className="text-slate-500"> · {fmt(h.changed_at)}</span>
                  {h.remarks && <p className="text-slate-600" lang="en">{h.remarks}</p>}
                </li>
              ))}
            </ol>
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{t("of.d.actions")}</p>
            {canPickOfficer ? (
              <div className="flex gap-2">
                <select aria-label={t("of.d.pickOfficer")} className="input py-1.5 text-sm" value={pick} onChange={(e) => setPick(e.target.value)}>
                  <option value="">{t("of.d.chooseOfficer")}</option>
                  {officers.map((o) => <option key={o.officer_id} value={o.officer_id}>{o.name} ({t("of.d.openN", { n: o.open_complaints })})</option>)}
                </select>
                <button disabled={!pick || busy} className="btn-secondary shrink-0" data-testid="assign-btn"
                  onClick={() => act(() => complaintsAPI.assign(id, pick, remarks || undefined), t("of.d.assigned"))}>
                  <UserCheck size={14} /> {t("of.d.assign")}
                </button>
              </div>
            ) : (
              <button disabled={busy} className="btn-secondary" data-testid="assign-me-btn"
                onClick={() => act(() => complaintsAPI.assign(id, undefined, remarks || undefined), t("of.d.assignedMe"))}>
                <UserCheck size={14} /> {t("of.d.assignMe")}
              </button>
            )}
            <label className="label" htmlFor="remarks">{t("of.d.remarks")}</label>
            <textarea id="remarks" className="input" rows={2} maxLength={500} value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder={t("of.d.remarksPh")} />
            {listItem.allowed_next.length === 0 ? (
              <p className="text-xs text-slate-500">{t("of.d.final")}</p>
            ) : (
              <div className="flex flex-wrap gap-2" role="group" aria-label={t("of.d.moveTo")}>
                {listItem.allowed_next.map((s: string) => (
                  <button key={s} disabled={busy} data-testid={`move-${s}`} className="btn-primary"
                    onClick={() => act(() => complaintsAPI.updateStatus(id, s, remarks || undefined), t("of.d.changed", { status: statusLabel(s) }))}>
                    {statusLabel(s)}
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
  const { t, label, apiError, dept } = useLang();
  const fmt = useFmt();
  const statusLabel = useStatusLabel();
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
      .then(setData).catch((e) => setError(apiError(e)));
  }, [filter, status, apiError]);
  useEffect(() => { if (user) load(); }, [user, load]);
  useEffect(() => { if (user && user.role !== "officer") complaintsAPI.officers().then(setOfficers).catch(() => setOfficers([])); }, [user]);

  if (!user) return <LoadingState />;
  const counts: Record<string, number> = data?.status_counts ?? {};
  const open = Object.entries(counts).filter(([s]) => !["resolved", "closed", "rejected"].includes(s)).reduce((a, [, v]) => a + v, 0);
  const slices = Object.entries(counts).map(([s, v]) => ({ label: statusLabel(s), value: v, color: STATUS_META[s]?.hex ?? "#94a3b8" }));
  const sel = data?.items.find((c: any) => c.complaint_id === selected);

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6" data-testid="officer-console">
      <header>
        <p className="text-sm text-slate-500 flex items-center gap-1"><Building2 size={14} /> {t("of.kicker")}</p>
        <h1 className="text-2xl font-black text-slate-900" data-testid="officer-scope">
          {data ? (data.department_name ? dept(data.department_name) : t("of.allDepartments")) : t("common.loading")}
        </h1>
        <p className="text-sm text-slate-500">{data?.department_scope ? t("of.scopeOwn") : t("of.scopeAll")}</p>
        {data?.demo_data_included && (
          <p className="mt-2 inline-flex rounded-lg bg-purple-50 border border-purple-200 px-3 py-1.5 text-xs text-purple-800" data-testid="demo-banner">
            {t("of.demoBanner")}
          </p>
        )}
      </header>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !data && <LoadingState />}

      {data && (
        <>
          <section aria-label={t("of.summary")} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard testId="o-open" label={t("of.s.open")} value={open} icon={<Hourglass size={18} />} />
            <StatCard testId="o-overdue" label={t("of.s.overdue")} value={data.overdue} tone={data.overdue ? "red" : "slate"} icon={<AlertTriangle size={18} />} />
            <StatCard testId="o-unassigned" label={t("of.s.unassigned")} value={data.unassigned} tone="amber" icon={<UserX size={18} />} />
            <StatCard testId="o-resolved" label={t("of.s.resolved")} value={(counts.resolved ?? 0) + (counts.closed ?? 0)} tone="green" icon={<CheckCircle2 size={18} />} />
          </section>

          <section className="card p-5 min-w-0" aria-labelledby="mix-h">
            <h2 id="mix-h" className="font-bold text-slate-900 mb-4">{t("of.byStatus")}</h2>
            {slices.length ? (
              <div className="grid md:grid-cols-2 gap-8 items-center">
                <DonutChart slices={slices} centerLabel={t("dash.chartCenter")} testId="officer-donut" />
                <BarList bars={slices.map((s) => ({ label: s.label, value: s.value, color: s.color }))} />
              </div>
            ) : <EmptyState message={t("of.noComplaints")} />}
          </section>

          <div>
            <section className="space-y-4 min-w-0" aria-labelledby="list-h">
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="list-h" className="font-bold text-slate-900 mr-2 flex items-center gap-2"><ClipboardList size={18} /> {t("of.complaints")}</h2>
                <div role="group" aria-label={t("of.assignmentFilter")} className="flex gap-2">
                  {([["all", "of.f.all"], ["mine", "of.f.mine"], ["unassigned", "of.f.unassigned"]] as const).map(([k, lk]) => (
                    <button key={k} aria-pressed={filter === k} onClick={() => setFilter(k)} data-testid={`filter-${k}`}
                      className={`px-3 py-1.5 rounded-full text-sm border ${filter === k ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200"}`}>{t(lk)}</button>
                  ))}
                </div>
                <select aria-label={t("of.filterStatus")} className="input w-auto py-1.5 text-sm ml-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="">{t("of.anyStatus")}</option>
                  {Object.keys(STATUS_META).map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}
                </select>
              </div>

              <div className={`grid gap-6 ${sel ? "xl:grid-cols-5" : ""}`}>
                <div className={`card overflow-x-auto min-w-0 ${sel ? "xl:col-span-3" : ""}`}>
                  {data.items.length === 0 ? <EmptyState message={t("of.noMatch")} /> : (
                    <table className="data-table text-xs">
                      <thead><tr><th>{t("of.col.ref")}</th><th>{t("of.col.subject")}</th><th>{t("of.col.priority")}</th><th>{t("of.col.status")}</th><th>{t("of.col.officer")}</th><th>{t("of.col.target")}</th></tr></thead>
                      <tbody>
                        {data.items.map((c: any) => (
                          <tr key={c.complaint_id} data-testid="staff-row" onClick={() => setSelected(c.complaint_id)}
                            className={`cursor-pointer ${selected === c.complaint_id ? "bg-brand-50" : ""}`}>
                            <td className="font-mono whitespace-nowrap">
                              <button className="underline text-brand-700" onClick={(e) => { e.stopPropagation(); setSelected(c.complaint_id); }}>{c.reference_number}</button>
                            </td>
                            <td className="max-w-[16rem] truncate" lang="en">{c.title}</td>
                            <td><span className={`badge ${PRIORITY[c.priority] ?? "badge-slate"}`}>{String(label("priority", c.priority))}</span></td>
                            <td><StatusBadge status={c.status} /></td>
                            <td lang="en">{c.officer_name ?? <span className="text-slate-500">—</span>}</td>
                            <td className={c.sla_breached ? "text-red-700 font-semibold whitespace-nowrap" : "whitespace-nowrap"}>{fmt(c.due_date)}{c.sla_breached ? ` ${t("of.past")}` : ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  <p className="text-xs text-slate-500 p-3">{t("of.footer", { total: data.total })}</p>
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
