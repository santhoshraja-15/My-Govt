"use client";

import { useState, useEffect } from "react";
import {
  Database, Activity, Table2, GitBranch, Search as SearchIcon,
  Play, BarChart3, Shield, RefreshCw, ChevronRight,
  CheckCircle2, AlertTriangle, XCircle, Loader2, Download,
  Server, Cpu, HardDrive, Zap
} from "lucide-react";
import { admin as adminAPI } from "@/lib/api";

// ── Sidebar items ──────────────────────────────────────────────
const NAV_ITEMS = [
  { key: "overview",   icon: BarChart3, label: "Overview" },
  { key: "schemas",    icon: Database,  label: "Schema Explorer" },
  { key: "query",      icon: Play,      label: "SQL Workspace" },
  { key: "datasets",   icon: HardDrive, label: "Datasets" },
  { key: "quality",    icon: Shield,    label: "Data Quality" },
  { key: "audit",      icon: Activity,  label: "Audit Logs" },
  { key: "graph",      icon: GitBranch, label: "Knowledge Graph" },
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
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
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
        <StatCard title="Total Records" value={stats.total_rows?.toLocaleString()} icon={Database} color="bg-brand-600" subtitle="Across all tables" />
        <StatCard title="Active Schemes" value={stats.schemes_count} icon={BarChart3} color="bg-emerald-600" subtitle="Tamil Nadu" />
        <StatCard title="Active Services" value={stats.services_count} icon={Zap} color="bg-amber-500" subtitle="e-Sevai" />
        <StatCard title="Complaints" value={stats.complaints_count} icon={Activity} color="bg-rose-500" subtitle="All time" />
      </div>

      {/* Service health */}
      {health && (
        <div className="card p-6">
          <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
            <Server size={18} className="text-brand-600" /> Service Health
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(health.services || {}).map(([svc, st]: any) => (
              <div key={svc} className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl">
                <HealthDot status={st.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 capitalize">{svc}</p>
                  <p className="text-xs text-slate-400">{st.latency_ms ? `${st.latency_ms}ms` : st.status}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dataset registry summary */}
      {data?.datasets?.length > 0 && (
        <div className="card p-6">
          <h2 className="font-bold text-slate-900 mb-4">Dataset Registry</h2>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr>
                <th>Dataset</th><th>Format</th><th>Records</th><th>Status</th><th>Quality</th>
              </tr></thead>
              <tbody>
                {data.datasets.slice(0,10).map((d: any) => (
                  <tr key={d.dataset_id}>
                    <td className="font-medium max-w-xs truncate">{d.dataset_name}</td>
                    <td><span className="badge badge-slate uppercase">{d.file_format}</span></td>
                    <td>{d.record_count?.toLocaleString()}</td>
                    <td><span className={`badge ${d.processing_status === "loaded" ? "badge-green" : "badge-yellow"}`}>{d.processing_status}</span></td>
                    <td>
                      <div className="flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                          <div className="h-full bg-emerald-500 rounded-full" style={{width: `${(d.quality_completeness||0)*100}%`}} />
                        </div>
                        <span className="text-xs text-slate-500">{Math.round((d.quality_completeness||0)*100)}%</span>
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
            {s.schema_name}
            <span className="ml-1.5 text-xs opacity-60">{s.table_count}</span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Table list */}
        <div className="card p-4 lg:col-span-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Tables in {selected}</p>
          <div className="space-y-1">
            {tables.map((t: any) => (
              <button key={t.table_name} onClick={() => selectTable(t.table_name)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-all ${
                  selectedTable === t.table_name ? "bg-brand-50 text-brand-700 font-semibold" : "text-slate-600 hover:bg-slate-50"}`}>
                <span className="truncate">{t.table_name}</span>
                <span className="text-xs text-slate-400 shrink-0 ml-1">{t.row_count_estimate?.toLocaleString()}</span>
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
                {tableDetail.row_count_estimate?.toLocaleString()} rows · {tableDetail.columns?.length} columns
              </p>
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr><th>Column</th><th>Type</th><th>Nullable</th><th>Default</th></tr></thead>
                  <tbody>
                    {tableDetail.columns?.map((c: any) => (
                      <tr key={c.column_name}>
                        <td className="font-mono text-xs font-semibold text-brand-700">{c.column_name}</td>
                        <td className="font-mono text-xs text-slate-500">{c.data_type}</td>
                        <td>{c.is_nullable === "YES" ? <span className="badge badge-slate">nullable</span> : <span className="badge badge-blue">required</span>}</td>
                        <td className="font-mono text-xs text-slate-400 max-w-xs truncate">{c.column_default}</td>
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
                Sample Data ({sample.rows.length} rows)
              </p>
              <div className="overflow-x-auto max-h-72">
                <table className="data-table text-xs">
                  <thead>
                    <tr>{sample.columns?.map((c: string) => <th key={c} className="whitespace-nowrap">{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {sample.rows.map((row: any[], ri: number) => (
                      <tr key={ri}>
                        {row.map((cell, ci) => (
                          <td key={ci} className="max-w-xs truncate font-mono">
                            {cell === null ? <span className="text-slate-300 italic">null</span> : String(cell)}
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
  const [sql, setSql] = useState("SELECT * FROM schemes.scheme LIMIT 10;");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await adminAPI.query(sql);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Query failed");
      setResult(null);
    }
    setLoading(false);
  };

  const EXAMPLES = [
    "SELECT count(*) FROM schemes.scheme WHERE status='active';",
    "SELECT s.scheme_code, s.name, count(r.rule_id) as rule_count FROM schemes.scheme s LEFT JOIN schemes.eligibility_rule r ON r.scheme_id=s.scheme_id GROUP BY s.scheme_id ORDER BY rule_count DESC LIMIT 10;",
    "SELECT c.status, count(*) FROM complaints.complaint c GROUP BY c.status;",
    "SELECT district_name, district_code FROM administration.district ORDER BY district_name;",
  ];

  return (
    <div className="animate-fade-in space-y-4">
      <div className="card p-4 bg-amber-50 border-amber-200 text-sm text-amber-700 flex items-start gap-2">
        <Shield size={16} className="shrink-0 mt-0.5" />
        Read-only workspace. Only SELECT queries are permitted. No DML operations allowed.
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold text-slate-700">SQL Query</p>
          <button onClick={run} disabled={loading} className="btn-primary py-1.5 text-sm">
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {loading ? "Running…" : "Run Query"}
          </button>
        </div>
        <textarea value={sql} onChange={e => setSql(e.target.value)}
          className="input font-mono text-sm resize-none" rows={5}
          placeholder="SELECT * FROM schemes.scheme LIMIT 10;" />

        <div className="mt-3">
          <p className="text-xs text-slate-400 mb-2">Quick examples:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex, i) => (
              <button key={i} onClick={() => setSql(ex)}
                className="text-xs bg-slate-50 hover:bg-brand-50 text-slate-500 hover:text-brand-700 px-3 py-1.5 rounded-lg border border-slate-200 transition-all font-mono">
                Example {i+1}
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
              {result.row_count} rows · {result.execution_time_ms}ms
            </p>
          </div>
          {result.rows?.length > 0 ? (
            <div className="overflow-x-auto max-h-96">
              <table className="data-table text-xs">
                <thead><tr>{result.columns?.map((c: string) => <th key={c} className="whitespace-nowrap">{c}</th>)}</tr></thead>
                <tbody>
                  {result.rows.map((row: any[], i: number) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="max-w-xs truncate font-mono">
                          {cell === null ? <span className="text-slate-300 italic">null</span> : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-400 py-4 text-center">Query executed — no rows returned.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Audit Logs ─────────────────────────────────────────────────
function AuditLogsPanel() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminAPI.auditLogs(50, 0)
      .then(res => setLogs(res.items || []))
      .catch(() => setLogs([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="card p-5">
        <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
          <Activity size={18} className="text-brand-600" /> Audit Logs
        </h2>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-600" /></div>
        ) : logs.length === 0 ? (
          <div className="text-center py-10 text-slate-400">No audit logs yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table text-xs">
              <thead><tr>
                <th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th><th>IP</th>
              </tr></thead>
              <tbody>
                {logs.map((log: any) => (
                  <tr key={log.audit_id}>
                    <td className="font-mono whitespace-nowrap">{new Date(log.created_at).toLocaleString("en-IN")}</td>
                    <td className="font-mono">{log.actor_email || log.actor_id?.slice(0,8) || "system"}</td>
                    <td><span className="badge badge-blue">{log.action}</span></td>
                    <td className="font-mono max-w-xs truncate">{log.resource_type} {log.resource_id?.slice(0,8)}</td>
                    <td>
                      {log.outcome === "success"
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
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminAPI.dataQuality().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const qMetrics = (dataset: any) => [
    { label: "Completeness", score: dataset.quality_completeness },
    { label: "Accuracy", score: dataset.quality_accuracy },
    { label: "Consistency", score: dataset.quality_consistency },
    { label: "Freshness", score: dataset.quality_freshness },
  ];

  return (
    <div className="animate-fade-in space-y-4">
      {loading ? (
        <div className="flex justify-center py-20"><Loader2 size={28} className="animate-spin text-brand-600" /></div>
      ) : !data?.datasets?.length ? (
        <div className="card p-10 text-center text-slate-400">No dataset quality data available.</div>
      ) : (
        data.datasets.map((d: any) => (
          <div key={d.dataset_id} className="card p-5">
            <div className="flex items-start justify-between mb-4 flex-wrap gap-2">
              <div>
                <h3 className="font-bold text-slate-900">{d.dataset_name}</h3>
                <p className="text-xs text-slate-400">{d.record_count?.toLocaleString()} records</p>
              </div>
              <span className={`badge ${d.validation_status === "validated" ? "badge-green" : "badge-yellow"}`}>
                {d.validation_status}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {qMetrics(d).map(({ label, score }) => (
                <div key={label} className="bg-slate-50 rounded-xl p-3 text-center">
                  <div className={`text-xl font-black mb-1 ${
                    (score||0) >= 0.9 ? "text-emerald-600" : (score||0) >= 0.7 ? "text-amber-500" : "text-red-500"
                  }`}>
                    {Math.round((score||0)*100)}%
                  </div>
                  <p className="text-xs text-slate-500">{label}</p>
                  <div className="w-full h-1.5 bg-slate-200 rounded-full mt-1.5 overflow-hidden">
                    <div className={`h-full rounded-full ${
                      (score||0) >= 0.9 ? "bg-emerald-500" : (score||0) >= 0.7 ? "bg-amber-400" : "bg-red-400"
                    }`} style={{width: `${(score||0)*100}%`}} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ── Knowledge Graph ────────────────────────────────────────────
function KnowledgeGraphPanel() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { adminAPI.kgStats().then(setStats).catch(() => {}); }, []);

  return (
    <div className="animate-fade-in card p-6">
      <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
        <GitBranch size={18} className="text-brand-600" /> Knowledge Graph (Neo4j)
      </h2>
      {!stats ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-600" /></div>
      ) : stats.status === "disabled" ? (
        <div className="text-center py-10 text-slate-400">Knowledge Graph feature is not enabled.</div>
      ) : stats.status !== "healthy" ? (
        <div className="text-center py-10 text-amber-500">Knowledge Graph unavailable: {stats.error}</div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="card p-4">
              <p className="text-xs text-slate-500 mb-2">Node Counts by Label</p>
              {Object.entries(stats.node_counts || {}).map(([label, count]: any) => (
                <div key={label} className="flex justify-between text-sm py-1 border-b border-slate-50">
                  <span className="font-medium text-slate-700">{label}</span>
                  <span className="font-bold text-brand-600">{count?.toLocaleString()}</span>
                </div>
              ))}
            </div>
            <div className="card p-4">
              <p className="text-xs text-slate-500 mb-2">Relationship Counts by Type</p>
              {Object.entries(stats.relationship_counts || {}).map(([type, count]: any) => (
                <div key={type} className="flex justify-between text-sm py-1 border-b border-slate-50">
                  <span className="font-medium text-slate-700">{type}</span>
                  <span className="font-bold text-brand-600">{count?.toLocaleString()}</span>
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
export default function AdminPage() {
  const [active, setActive] = useState("overview");
  const [collapsed, setCollapsed] = useState(false);

  const PANELS: Record<string, React.ReactNode> = {
    overview: <OverviewPanel />,
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
                <p className="font-bold text-slate-900 text-sm">Admin Console</p>
                <p className="text-xs text-slate-400">Intelligence Hub</p>
              </div>
            </>
          )}
          <button onClick={() => setCollapsed(c => !c)}
            className={`ml-auto btn-ghost p-1.5 ${collapsed ? "mx-auto" : ""}`}>
            <ChevronRight size={16} className={`transition-transform ${collapsed ? "" : "rotate-180"}`} />
          </button>
        </div>

        <nav className="flex-1 p-2 space-y-0.5">
          {NAV_ITEMS.map(({ key, icon: Icon, label }) => (
            <button key={key} onClick={() => setActive(key)}
              className={`admin-sidebar-item w-full ${active === key ? "active" : ""} ${collapsed ? "justify-center px-2" : ""}`}
              title={collapsed ? label : undefined}>
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span>{label}</span>}
            </button>
          ))}
        </nav>

        <div className="p-2 border-t border-slate-100">
          <a href="/" className={`admin-sidebar-item w-full ${collapsed ? "justify-center px-2" : ""}`}>
            <ChevronRight size={18} className="rotate-180 shrink-0" />
            {!collapsed && <span>Exit Admin</span>}
          </a>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 flex flex-col">
        <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-10">
          <h1 className="font-bold text-slate-900 text-lg capitalize">
            {NAV_ITEMS.find(n => n.key === active)?.label || "Dashboard"}
          </h1>
        </header>
        <div className="flex-1 p-6 overflow-auto">
          {PANELS[active]}
        </div>
      </main>
    </div>
  );
}
