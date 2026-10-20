"use client";

import { useState, useEffect } from "react";
import {
  Database, Activity, Table2, GitBranch, Search as SearchIcon,
  Play, BarChart3, Shield, RefreshCw, ChevronRight,
  CheckCircle2, AlertTriangle, XCircle, Loader2, Download,
  Server, Cpu, HardDrive, Zap
} from "lucide-react";
import { admin as adminAPI } from "@/lib/api";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { LoadingState } from "@/components/ui/AsyncState";
import { ComplaintsPanel, DepartmentPerformancePanel, VerificationQueuePanel } from "@/components/admin/OperationsPanels";
import { useLang, type TKey } from "@/lib/i18n";

/** Quality scores are stored on a 0-100 scale in the dataset registry. */
const pct = (v: unknown) => Math.max(0, Math.min(100, Math.round(Number(v) || 0)));

// ── Sidebar items ──────────────────────────────────────────────
const NAV_ITEMS = [
  { key: "overview",   icon: BarChart3, label: "ad.nav.overview" as TKey },
  { key: "complaints", icon: Activity,  label: "ad.nav.complaints" as TKey },
  { key: "departments", icon: BarChart3, label: "ad.nav.departments" as TKey },
  { key: "verification", icon: CheckCircle2, label: "ad.nav.verification" as TKey },
  { key: "schemas",    icon: Database,  label: "ad.nav.schemas" as TKey },
  { key: "query",      icon: Play,      label: "ad.nav.query" as TKey, systemOnly: true },
  { key: "datasets",   icon: HardDrive, label: "ad.nav.datasets" as TKey },
  { key: "quality",    icon: Shield,    label: "ad.nav.quality" as TKey },
  { key: "audit",      icon: Activity,  label: "ad.nav.audit" as TKey },
  { key: "graph",      icon: GitBranch, label: "ad.nav.graph" as TKey },
];

// ── Stat card ──────────────────────────────────────────────────
function StatCard({ title, value, subtitle, icon: Icon, color }: any) {
  return (
    <div className="card p-5 flex items-start gap-4">
      <div className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-500 font-medium mb-0.5">{title}</p>
        <p className="text-2xl font-black text-slate-900">{value ?? "—"}</p>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

// ── Health dot ─────────────────────────────────────────────────
function HealthDot({ status }: { status: string }) {
  const ok = status === "healthy" || status === "ok";
  const warn = status === "degraded";
  return (
    <span className={`w-2.5 h-2.5 rounded-full inline-block ${ok ? "bg-emerald-500" : warn ? "bg-amber-400" : "bg-red-500"}`} />
  );
}

// ── Overview ───────────────────────────────────────────────────
function OverviewPanel() {
  const { t, fmtNumber, label } = useLang();
  const [data, setData] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([adminAPI.overview(), adminAPI.health()])
      .then(([ov, hl]) => { setData(ov); setHealth(hl); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-600" /></div>;

  const stats = data?.database_stats || {};
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("ad.ov.schemes")} value={stats.schemes} icon={BarChart3} color="bg-emerald-600" subtitle={t("ad.ov.live")} />
        <StatCard title={t("ad.ov.services")} value={stats.services} icon={Zap} color="bg-amber-500" subtitle={t("ad.ov.live")} />
        <StatCard title={stats.demo_data_included ? t("ad.ov.complaintsDemo") : t("ad.ov.complaintsReal")} value={stats.complaints_total} icon={Activity} color="bg-rose-500" subtitle={t("ad.ov.openN", { n: stats.complaints_open ?? "—" })} />
        <StatCard title={t("ad.ov.sla")} value={stats.complaints_sla_breached} icon={AlertTriangle} color="bg-red-600" subtitle={t("ad.ov.noAuthority", { n: stats.complaints_unassigned ?? "—" })} />
      </div>

      <div className="card p-6" data-testid="verification-breakdown">
        <h2 className="font-bold text-slate-900 mb-1">{t("ad.ov.verifTitle")}</h2>
        <p className="text-xs text-slate-500 mb-4">{t("ad.ov.verifNote")}</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          {Object.entries(data?.verification || {}).map(([k, v]: any) => (
            <div key={k}>
              <p className="font-semibold capitalize">{label("ad.vq.kind", k.replace(/s$/, ""))}</p>
              {v ? Object.entries(v).map(([status, n]: any) => <p key={status} className="text-slate-600">{label("vs", status)}: {n}</p>) : <p className="text-slate-500">{t("ad.ov.unavailable")}</p>}
            </div>
          ))}
        </div>
        {stats.synthetic_complaints > 0 && <p className="text-xs text-amber-700 mt-3" data-testid="synthetic-note">{stats.demo_data_included
          ? t("ad.ov.synthIncluded", { n: stats.synthetic_complaints })
          : t("ad.ov.synthExcluded", { n: stats.synthetic_complaints })}</p>}
      </div>

      {/* Service health */}
      {health && (
        <div className="card p-6">
          <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
            <Server size={18} className="text-brand-600" /> {t("ad.ov.health")}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(health.services || {}).map(([svc, st]: any) => (
              <div key={svc} className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <HealthDot status={st.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 capitalize" lang="en">{svc}</p>
                  <p className="text-xs text-slate-500">{st.latency_ms ? `${st.latency_ms}ms` : label("hs", st.status)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dataset registry summary */}
      {data?.datasets?.length > 0 && (
        <div className="card p-6">
          <h2 className="font-bold text-slate-900 mb-4">{t("ad.ov.registry")}</h2>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr>
                <th>{t("ad.ov.col.dataset")}</th><th>{t("ad.ov.col.format")}</th><th>{t("ad.ov.col.records")}</th><th>{t("ad.ov.col.status")}</th><th>{t("ad.ov.col.quality")}</th>
              </tr></thead>
              <tbody>
                {data.datasets.slice(0,10).map((d: any) => (
                  <tr key={d.dataset_id}>
                    <td className="font-medium max-w-xs truncate" lang="en">{d.dataset_name}</td>
                    <td><span className="badge badge-slate uppercase" lang="en">{d.file_format}</span></td>
                    <td>{d.record_count != null ? fmtNumber(d.record_count) : ""}</td>
                    <td><span className={`badge ${d.processing_status === "loaded" ? "badge-green" : "badge-yellow"}`}>{label("ds", d.processing_status)}</span></td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 rounded-full" style={{width: `${pct(d.quality_completeness)}%`}} />
                        </div>
                        <span className="text-xs text-slate-500">{pct(d.quality_completeness)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Schema Explorer ────────────────────────────────────────────
function SchemaExplorer() {
  const { t, fmtNumber } = useLang();
  const [schemas, setSchemas] = useState<any[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [tables, setTables] = useState<any[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [tableDetail, setTableDetail] = useState<any>(null);
  const [sample, setSample] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    adminAPI.schemas().then(s => { setSchemas(s); if (s[0]) setSelected(s[0].schema_name); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    adminAPI.tables(selected).then(setTables).catch(() => setTables([]));
    setSelectedTable("");
    setTableDetail(null);
    setSample(null);
  }, [selected]);

  const selectTable = async (tbl: string) => {
    setSelectedTable(tbl);
    setLoading(true);
    try {
      const [detail, sampleData] = await Promise.all([
        adminAPI.tableDetail(selected, tbl),
        adminAPI.tableSample(selected, tbl, 20, 0),
      ]);
      setTableDetail(detail);
      setSample(sampleData);
    } catch {}
    setLoading(false);
  };

  return (
    <div className="animate-fade-in">
      <div className="flex gap-2 mb-5 flex-wrap">
        {schemas.map((s: any) => (
          <button key={s.schema_name} onClick={() => setSelected(s.schema_name)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-all ${
              selected === s.schema_name ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-brand-300"}`}>
            <span className="font-mono">{s.schema_name}</span>
            <span className="ml-1.5 text-xs opacity-60">{s.table_count}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Table list */}
        <div className="card p-4 lg:col-span-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">{t("ad.sc.tablesIn")} <span className="font-mono normal-case">{selected}</span></p>
          <div className="space-y-1">
            {tables.map((tb: any) => (
              <button key={tb.table_name} onClick={() => selectTable(tb.table_name)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-all ${
                  selectedTable === tb.table_name ? "bg-brand-50 text-brand-700 font-semibold" : "text-slate-600 hover:bg-slate-50"}`}>
                <span className="truncate font-mono">{tb.table_name}</span>
                <span className="text-xs text-slate-500 shrink-0 ml-1">{tb.row_count_estimate != null ? fmtNumber(tb.row_count_estimate) : ""}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Table detail */}
        <div className="lg:col-span-3 space-y-4">
          {loading && <div className="flex justify-center py-12"><Loader2 size={24} className="animate-spin text-brand-600" /></div>}

          {tableDetail && !loading && (
            <div className="card p-5">
              <h3 className="font-bold text-slate-900 mb-1">{selected}.{selectedTable}</h3>
              <p className="text-sm text-slate-500 mb-4">
                {t("ad.sc.rowsEst", { rows: fmtNumber(tableDetail.estimated_rows ?? 0), cols: tableDetail.columns?.length ?? 0 })}
              </p>
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr><th>{t("ad.sc.col.column")}</th><th>{t("ad.sc.col.type")}</th><th>{t("ad.sc.col.nullable")}</th><th>{t("ad.sc.col.default")}</th></tr></thead>
                  <tbody>
                    {tableDetail.columns?.map((c: any) => (
                      <tr key={c.column_name}>
                        <td className="font-mono text-xs font-semibold text-brand-700">{c.column_name}</td>
                        <td className="font-mono text-xs text-slate-500">{c.data_type}</td>
                        <td>{c.is_nullable === "YES" ? <span className="badge badge-slate">{t("ad.sc.nullable")}</span> : <span className="badge badge-blue">{t("ad.sc.required")}</span>}</td>
                        <td className="font-mono text-xs text-slate-500 max-w-xs truncate">{c.column_default}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {sample && !loading && sample.rows?.length > 0 && (
            <div className="card p-5">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
                {t("ad.sc.sample", { n: sample.rows.length })}
              </p>
              <div className="overflow-x-auto max-h-72">
                <table className="data-table text-xs">
                  <thead>
                    <tr>{sample.columns?.map((c: string) => <th key={c} className="whitespace-nowrap">{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {sample.rows.map((row: Record<string, any>, ri: number) => (
                      <tr key={ri}>
                        {sample.columns.map((col: string, ci: number) => (
                          <td key={ci} className="max-w-xs truncate font-mono">
                            {row[col] === null ? <span className="text-slate-300 italic">null</span> : String(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── SQL Workspace ──────────────────────────────────────────────
function SQLWorkspace() {
  const { t, apiError } = useLang();
  const [sql, setSql] = useState("SELECT * FROM schemes.scheme LIMIT 10;");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await adminAPI.query(sql);
      if (res.error) { setError(res.error); setResult(null); } else { setResult(res); }
    } catch (e: any) {
      setError(e?.status ? apiError(e) : t("ad.q.failed"));
      setResult(null);
    }
    setLoading(false);
  };

  const EXAMPLES = [
    "SELECT count(*) FROM schemes.scheme WHERE status='active';",
    "SELECT s.scheme_code, s.scheme_name, count(r.rule_id) as rule_count FROM schemes.scheme s LEFT JOIN schemes.eligibility_rule r ON r.scheme_id=s.scheme_id GROUP BY s.scheme_id ORDER BY rule_count DESC LIMIT 10;",
    "SELECT c.status, count(*) FROM complaints.complaint c GROUP BY c.status;",
    "SELECT district_name, district_code FROM administration.district ORDER BY district_name;",
  ];

  return (
    <div className="animate-fade-in space-y-4">
      <div className="card p-4 bg-amber-50 border-amber-200 text-sm text-amber-700 flex items-start gap-2">
        <Shield size={16} className="shrink-0 mt-0.5" />
        {t("ad.q.readonly")}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-slate-700">{t("ad.q.title")}</p>
          <button onClick={run} disabled={loading} className="btn-primary py-1.5 text-sm">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {loading ? t("ad.q.running") : t("ad.q.run")}
          </button>
        </div>
        <textarea value={sql} onChange={e => setSql(e.target.value)} aria-label={t("ad.q.aria")}
          className="input font-mono text-sm resize-none" rows={5}
          placeholder="SELECT * FROM schemes.scheme LIMIT 10;" />

        <div className="mt-3">
          <p className="text-xs text-slate-500 mb-2">{t("ad.q.examples")}</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex, i) => (
              <button key={i} onClick={() => setSql(ex)}
                className="text-xs bg-slate-50 hover:bg-brand-50 text-slate-500 hover:text-brand-700 px-3 py-1.5 rounded-lg border border-slate-200 transition-all font-mono">
                {t("ad.q.example", { n: i + 1 })}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="card p-4 bg-red-50 border-red-200 text-sm text-red-700 font-mono">
          {error}
        </div>
      )}

      {result && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              {t("ad.q.rows", { rows: result.row_count, ms: result.execution_time_ms })}
            </p>
          </div>
          {result.rows?.length > 0 ? (
            <div className="overflow-x-auto max-h-96">
              <table className="data-table text-xs">
                <thead><tr>{result.columns?.map((c: string) => <th key={c} className="whitespace-nowrap">{c}</th>)}</tr></thead>
                <tbody>
                  {result.rows.map((row: Record<string, any>, i: number) => (
                    <tr key={i}>
                      {result.columns.map((col: string, j: number) => { const cell = row[col]; return (
                        <td key={j} className="max-w-xs truncate font-mono">
                          {cell === null ? <span className="text-slate-300 italic">null</span> : String(cell)}
                        </td>
                      ); })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500 py-4 text-center">{t("ad.q.noRows")}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Audit Logs ─────────────────────────────────────────────────
function AuditLogsPanel() {
  const { t, lang } = useLang();
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminAPI.auditLogs(50, 0)
      .then(res => setLogs(res.rows || []))
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="card p-5">
        <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
          <Activity size={18} className="text-brand-600" /> {t("ad.au.title")}
        </h2>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-600" /></div>
        ) : logs.length === 0 ? (
          <div className="text-center py-10 text-slate-500">{t("ad.au.none")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table text-xs">
              <thead><tr>
                <th>{t("ad.au.col.time")}</th><th>{t("ad.au.col.actor")}</th><th>{t("ad.au.col.action")}</th><th>{t("ad.au.col.resource")}</th><th>{t("ad.au.col.outcome")}</th><th>{t("ad.au.col.ip")}</th>
              </tr></thead>
              <tbody>
                {logs.map((log: any) => (
                  <tr key={log.log_id}>
                    <td className="font-mono whitespace-nowrap">{new Date(log.created_at).toLocaleString(lang === "ta" ? "ta-IN" : "en-IN")}</td>
                    <td>{log.actor_role || log.actor_id ? <span className="font-mono">{log.actor_role ? `${log.actor_role} ` : ""}{log.actor_id?.slice(0,8)}</span> : t("ad.au.anonymous")}</td>
                    <td><span className="badge badge-blue" lang="en">{log.action}</span></td>
                    <td className="font-mono max-w-xs truncate">{log.entity_type} {log.entity_id?.slice(0,12)}</td>
                    <td>
                      {log.outcome !== "failure"
                        ? <span className="badge badge-green">✓</span>
                        : <span className="badge badge-red">✗</span>}
                    </td>
                    <td className="font-mono">{log.ip_address || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Data Quality ───────────────────────────────────────────────
function DataQualityPanel() {
  const { t, fmtNumber, label } = useLang();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminAPI.dataQuality().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const qMetrics = (dataset: any) => [
    { label: t("ad.dq.completeness"), score: dataset.quality_completeness },
    { label: t("ad.dq.accuracy"), score: dataset.quality_accuracy },
    { label: t("ad.dq.consistency"), score: dataset.quality_consistency },
    { label: t("ad.dq.freshness"), score: dataset.quality_freshness },
  ];

  return (
    <div className="animate-fade-in space-y-4">
      {loading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-600" /></div>
      ) : !data?.datasets?.length ? (
        <div className="card p-10 text-center text-slate-500">{t("ad.dq.none")}</div>
      ) : (
        <>
        <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" data-testid="quality-disclaimer">
          {t("ad.dq.disclaimer")}
        </p>
        {data.datasets.map((d: any) => (
          <div key={d.dataset_id} className="card p-5">
            <div className="flex items-start justify-between mb-4 flex-wrap gap-2">
              <div>
                <h3 className="font-bold text-slate-900" lang="en">{d.dataset_name}</h3>
                <p className="text-xs text-slate-500">{t("ad.dq.records", { n: d.record_count != null ? fmtNumber(d.record_count) : 0 })}</p>
              </div>
              <span className={`badge ${d.validation_status === "validated" ? "badge-green" : "badge-yellow"}`}>
                {label("ds", d.validation_status)}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {qMetrics(d).map(({ label, score }) => (
                <div key={label} className="bg-slate-50 rounded-xl p-3 text-center">
                  <div className={`text-xl font-black mb-1 ${
                    pct(score) >= 90 ? "text-emerald-700" : pct(score) >= 70 ? "text-amber-700" : "text-red-700"
                  }`}>
                    {pct(score)}%
                  </div>
                  <p className="text-xs text-slate-500">{label}</p>
                  <div className="w-full h-1.5 bg-slate-200 rounded-full mt-1.5 overflow-hidden">
                    <div className={`h-full rounded-full ${
                      pct(score) >= 90 ? "bg-emerald-500" : pct(score) >= 70 ? "bg-amber-400" : "bg-red-400"
                    }`} style={{width: `${pct(score)}%`}} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        </>
      )}
    </div>
  );
}

// ── Knowledge Graph ────────────────────────────────────────────
function KnowledgeGraphPanel() {
  const { t, fmtNumber } = useLang();
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { adminAPI.kgStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="animate-fade-in card p-6">
      <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
        <GitBranch size={18} className="text-brand-600" /> {t("ad.kg.title")}
      </h2>
      {!stats ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-600" /></div>
      ) : stats.status === "disabled" ? (
        <div className="text-center py-10 text-slate-500">{t("ad.kg.disabled")}</div>
      ) : stats.status !== "healthy" ? (
        <div className="text-center py-10 text-amber-500">{t("ad.kg.unavailable")}</div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="card p-4">
              <p className="text-xs text-slate-500 mb-2">{t("ad.kg.nodes")}</p>
              {Object.entries(stats.node_counts || {}).map(([label, count]: any) => (
                <div key={label} className="flex justify-between text-sm py-1 border-b border-slate-50">
                  <span className="font-medium text-slate-700">{label}</span>
                  <span className="font-bold text-brand-600">{count != null ? fmtNumber(count) : ""}</span>
                </div>
              ))}
            </div>
            <div className="card p-4">
              <p className="text-xs text-slate-500 mb-2">{t("ad.kg.rels")}</p>
              {Object.entries(stats.relationship_counts || {}).map(([type, count]: any) => (
                <div key={type} className="flex justify-between text-sm py-1 border-b border-slate-50">
                  <span className="font-medium text-slate-700">{type}</span>
                  <span className="font-bold text-brand-600">{count != null ? fmtNumber(count) : ""}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main admin layout ──────────────────────────────────────────
function AdminConsole() {
  const { user } = useAuth();
  const { t } = useLang();
  const navItems = NAV_ITEMS.filter((n: any) => !n.systemOnly || user?.role === "system_admin");
  const [active, setActive] = useState("overview");
  const [collapsed, setCollapsed] = useState(false);

  const PANELS: Record<string, React.ReactNode> = {
    overview: <OverviewPanel />,
    complaints: <ComplaintsPanel />,
    departments: <DepartmentPerformancePanel />,
    verification: <VerificationQueuePanel />,
    schemas:  <SchemaExplorer />,
    query:    <SQLWorkspace />,
    datasets: <DataQualityPanel />,
    quality:  <DataQualityPanel />,
    audit:    <AuditLogsPanel />,
    graph:    <KnowledgeGraphPanel />,
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <aside className={`${collapsed ? "w-16" : "w-60"} bg-white border-r border-slate-200 flex flex-col transition-all duration-200 shrink-0`}>
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-100">
          {!collapsed && (
            <>
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-600 to-teal-600 flex items-center justify-center">
                <Database size={16} className="text-white" />
              </div>
              <div>
                <p className="font-bold text-slate-900 text-sm">{t("ad.console")}</p>
                <p className="text-xs text-slate-500">{t("ad.hub")}</p>
              </div>
            </>
          )}
          <button onClick={() => setCollapsed(c => !c)} aria-label={collapsed ? t("ad.expand") : t("ad.collapse")}
            className={`ml-auto btn-ghost p-1.5 ${collapsed ? "mx-auto" : ""}`}>
            <ChevronRight size={16} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ key, icon: Icon, label }) => (
            <button key={key} onClick={() => setActive(key)}
              className={`admin-sidebar-item w-full ${active === key ? "active" : ""} ${collapsed ? "justify-center px-2" : ""}`}
              title={collapsed ? t(label) : undefined}>
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{t(label)}</span>}
            </button>
          ))}
        </nav>

        <div className="p-2 border-t border-slate-100 space-y-1">
          <Link href="/database-architecture" data-testid="admin-database-architecture"
            className={`admin-sidebar-item w-full bg-brand-50 text-brand-700 font-semibold ${collapsed ? "justify-center px-2" : ""}`}>
            <Database size={18} className="shrink-0" />
            {!collapsed && <span>{t("nav.architecture")}</span>}
          </Link>
          <Link href="/" className={`admin-sidebar-item w-full ${collapsed ? "justify-center px-2" : ""}`}>
            <ChevronRight size={18} className="rotate-180 shrink-0" />
            {!collapsed && <span>{t("ad.exit")}</span>}
          </Link>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
          <h1 className="font-bold text-slate-900 text-lg capitalize">
            {t(NAV_ITEMS.find(n => n.key === active)?.label || "ad.dashboard")}
          </h1>
        </header>
        <div className="flex-1 p-6 overflow-auto">
          {PANELS[active]}
        </div>
      </main>
    </div>
  );
}

/** Route guard: only state/system administrators see the console; everyone else gets an explanation. */
export default function AdminPage() {
  const { user, loading, isAdmin } = useAuth();
  const { t } = useLang();
  if (loading) return <LoadingState />;
  if (!user) {
    return (
      <main className="max-w-md mx-auto px-4 py-16 text-center" data-testid="admin-login-required">
        <h1 className="text-xl font-bold mb-3">{t("ad.signinRequired")}</h1>
        <Link href="/login?next=/admin" className="btn-primary">{t("auth.signin")}</Link>
      </main>
    );
  }
  if (!isAdmin) {
    return (
      <main className="max-w-md mx-auto px-4 py-16 text-center" data-testid="admin-forbidden">
        <h1 className="text-xl font-bold mb-3">{t("ad.denied")}</h1>
        <p className="text-slate-600">{t("ad.deniedText")}</p>
      </main>
    );
  }
  return <AdminConsole />;
}
