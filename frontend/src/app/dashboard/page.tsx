"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowRight, ClipboardList, FileSearch, MessageSquare, PlusCircle, Sparkles, Timer, CheckCircle2, Hourglass } from "lucide-react";
import { complaints as complaintsAPI, publicStats, schemes as schemesAPI } from "@/lib/api";
import { useGuard } from "@/lib/useGuard";
import { DonutChart, StatCard } from "@/components/ui/charts";
import { StatusBadge, STATUS_META } from "@/components/ui/StatusBadge";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { useLang } from "@/lib/i18n";

const TERMINAL = ["resolved", "closed", "rejected"];

export default function DashboardPage() {
  const { t, names, fmtDate, apiError } = useLang();
  const fmt = (d?: string | null) => (d ? fmtDate(d) : "—");
  const user = useGuard((r) => r === "citizen");
  const [mine, setMine] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [featured, setFeatured] = useState<any[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError(""); setMine(null);
    complaintsAPI.mine({ page_size: 100 }).then(setMine).catch((e) => setError(apiError(e)));
    publicStats.get().then(setStats).catch(() => setStats(null));
    schemesAPI.list({ page_size: 4 }).then((r) => setFeatured(r.items ?? [])).catch(() => setFeatured([]));
  }, [apiError]);
  useEffect(() => { if (user) load(); }, [user, load]);

  if (!user) return <LoadingState />;

  const items: any[] = mine?.items ?? [];
  const open = items.filter((c) => !TERMINAL.includes(c.status));
  const overdue = open.filter((c) => c.due_date && new Date(c.due_date) < new Date());
  const resolved = items.filter((c) => c.status === "resolved" || c.status === "closed");
  const counts: Record<string, number> = {};
  items.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });
  const slices = Object.entries(counts).map(([s, v]) => ({ label: STATUS_META[s]?.key ? t(STATUS_META[s].key!) : s, value: v, color: STATUS_META[s]?.hex ?? "#94a3b8" }));
  const first = (user.full_name || user.email).split(" ")[0];

  return (
    <main className="max-w-6xl mx-auto px-4 py-8 space-y-8" data-testid="citizen-dashboard">
      <header className="rounded-3xl hero-gradient text-white p-6 sm:p-8 animate-fade-in">
        <p className="text-blue-100 text-sm">{t("dash.kicker")}</p>
        <h1 className="text-2xl sm:text-3xl font-black mt-1" data-testid="dashboard-greeting">{t("dash.welcome", { name: first })}</h1>
        <p className="text-blue-100 mt-2 max-w-2xl text-sm">
          {t("dash.intro")}
        </p>
        <div className="flex flex-wrap gap-3 mt-5">
          <Link href="/complaints" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shadow-saffron-500/30"><PlusCircle size={16} /> {t("dash.file")}</Link>
          <Link href="/schemes" className="btn-primary bg-white/15 hover:bg-white/25 shadow-none"><FileSearch size={16} /> {t("dash.browse")}</Link>
          <Link href="/assistant" className="btn-primary bg-white/15 hover:bg-white/25 shadow-none"><MessageSquare size={16} /> {t("dash.ask")}</Link>
        </div>
      </header>

      {error && <ErrorState message={error} onRetry={load} />}
      {!error && !mine && <LoadingState label={t("dash.loadingComplaints")} />}

      {mine && (
        <>
          <section aria-label={t("dash.summary")} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard testId="stat-total" label={t("dash.mine")} value={items.length} icon={<ClipboardList size={18} />} />
            <StatCard testId="stat-open" label={t("dash.open")} value={open.length} tone="amber" icon={<Hourglass size={18} />} hint={t("dash.openHint")} />
            <StatCard testId="stat-overdue" label={t("dash.overdue")} value={overdue.length} tone={overdue.length ? "red" : "slate"} icon={<Timer size={18} />} hint={t("dash.overdueHint")} />
            <StatCard testId="stat-resolved" label={t("dash.resolved")} value={resolved.length} tone="green" icon={<CheckCircle2 size={18} />} />
          </section>

          <div className="grid lg:grid-cols-5 gap-6">
            <section className="card p-5 lg:col-span-3 min-w-0" aria-labelledby="recent-h">
              <div className="flex items-center justify-between mb-4">
                <h2 id="recent-h" className="font-bold text-slate-900">{t("dash.recent")}</h2>
                <Link href="/complaints" className="text-sm text-brand-700 flex items-center gap-1">{t("dash.all")} <ArrowRight size={14} /></Link>
              </div>
              {items.length === 0 ? (
                <EmptyState message={t("dash.none")} />
              ) : (
                <ul className="divide-y divide-slate-100" data-testid="recent-complaints">
                  {items.slice(0, 6).map((c) => (
                    <li key={c.complaint_id} className="py-3 flex flex-wrap items-center gap-3 justify-between">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-800 truncate">{c.title}</p>
                        <p className="text-xs text-slate-500"><span className="font-mono">{c.reference_number}</span> · {t("dash.filed", { date: fmt(c.created_at) })}{c.department_name ? ` · ${c.department_name}` : ""}</p>
                      </div>
                      <StatusBadge status={c.status} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card p-5 lg:col-span-2 min-w-0" aria-labelledby="mix-h">
              <h2 id="mix-h" className="font-bold text-slate-900 mb-4">{t("dash.overview")}</h2>
              {slices.length === 0 ? <EmptyState message={t("dash.nothingToChart")} /> : <DonutChart slices={slices} centerLabel={t("dash.chartCenter")} testId="status-donut" />}
            </section>
          </div>
        </>
      )}

      <section aria-labelledby="schemes-h" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="schemes-h" className="font-bold text-slate-900 flex items-center gap-2"><Sparkles size={18} className="text-saffron-500" /> {t("dash.explore")}</h2>
          <Link href="/schemes" className="text-sm text-brand-700 flex items-center gap-1">{stats ? t("dash.seeAllN", { count: stats.schemes }) : t("dash.seeAll")} <ArrowRight size={14} /></Link>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {featured.map((s) => (
            <Link key={s.scheme_id} href={`/schemes/${s.scheme_id}`} className="card p-4 block" data-testid="featured-scheme">
              <p className="font-semibold text-slate-800 text-sm line-clamp-2">{names(s.name, s.name_ta).primary}</p>
              {names(s.name, s.name_ta).secondary && <p className="text-xs text-slate-500 line-clamp-1">{names(s.name, s.name_ta).secondary}</p>}
              <div className="mt-3 flex items-center justify-between">
                <VerificationBadge status={s.verification_status} />
                <span className="text-xs text-brand-700 flex items-center gap-1">{t("dash.eligibility")} <ArrowRight size={12} /></span>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
