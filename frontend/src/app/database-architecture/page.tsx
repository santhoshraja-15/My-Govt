"use client";

import { useEffect, useState } from "react";
import { Boxes, Database, GitFork, KeyRound, Layers, Rows3, Table2 } from "lucide-react";
import { architectureApi, STATUS_STYLE } from "@/lib/architecture";
import { useGuard } from "@/lib/useGuard";
import { StatCard } from "@/components/ui/charts";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { ArchitectureDiagram } from "@/components/architecture/ArchitectureDiagram";
import { ErDiagram } from "@/components/architecture/ErDiagram";
import { TableDetail } from "@/components/architecture/TableDetail";
import { AdvancedPanel, ImplementationPanel, PanelSkeleton, RelationalSchemaPanel, useAsync } from "@/components/architecture/Panels";

const TABS = [
  ["architecture", "Architecture"], ["er", "ER Diagram"], ["schema", "Relational Schema"], ["implementation", "Implementation"], ["advanced", "Advanced Concepts"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function DatabaseArchitecturePage() {
  const user = useGuard((r) => r === "state_admin" || r === "system_admin");
  const [tab, setTab] = useState<Tab>("architecture");
  const [selected, setSelected] = useState<string | null>(null);
  const ok = !!user;                               // no API calls until the guard has confirmed an administrator
  const overview = useAsync(() => architectureApi.overview(), [user?.user_id], ok);
  const components = useAsync(() => architectureApi.components(), [user?.user_id], ok);
  const tables = useAsync(() => architectureApi.tables(), [user?.user_id], ok);
  const rels = useAsync(() => architectureApi.relationships(), [user?.user_id], ok);

  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    if (t && TABS.some(([k]) => k === t)) setTab(t);
  }, []);
  const choose = (t: Tab) => { setTab(t); window.history.replaceState(null, "", `?tab=${t}`); };

  if (!user) return <LoadingState />;
  const o = overview.data;
  const failed = overview.error || tables.error || rels.error || components.error;

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6" data-testid="database-architecture">
      <header className="rounded-3xl hero-gradient text-white p-6 sm:p-8">
        <p className="text-blue-100 text-sm flex items-center gap-2"><Database size={16} aria-hidden /> Technical overview</p>
        <h1 className="text-2xl sm:text-3xl font-black mt-1">Database Architecture Explorer</h1>
        <p className="text-blue-100 mt-2 max-w-3xl text-sm">
          How MyGovt stores and connects its data. Everything on this page is read live from the running database&apos;s catalog and from the backend source tree — nothing is a
          hand-drawn diagram. PostgreSQL is the single system of record; PostGIS and pgvector are extensions inside it; Neo4j, Redis and MinIO are optional.
        </p>
        {o && (
          <ul className="flex flex-wrap gap-2 mt-4" aria-label="Data technologies" data-testid="technology-list">
            {o.technologies.map((t: any) => {
              const st = STATUS_STYLE[t.status] ?? STATUS_STYLE.unknown;
              return <li key={t.name} className={`badge ${st.cls} gap-1 max-w-full truncate`} title={`${t.name} — ${t.role}`} data-status={t.status}>{t.name} · {st.label}</li>;
            })}
          </ul>
        )}
      </header>

      {failed && <ErrorState message={failed} onRetry={() => { overview.reload(); tables.reload(); rels.reload(); components.reload(); }} />}

      {o ? (
        <section aria-label="Totals" className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4" data-testid="kpi-grid">
          <StatCard testId="kpi-engines" label="Data technologies" value={o.counts.data_technologies} icon={<Boxes size={18} />} hint="PostgreSQL + extensions + optional" />
          <StatCard testId="kpi-schemas" label="Schemas" value={o.counts.schemas} icon={<Layers size={18} />} tone="green" />
          <StatCard testId="kpi-tables" label="Tables" value={o.counts.tables} icon={<Table2 size={18} />} />
          <StatCard testId="kpi-columns" label="Columns" value={o.counts.columns} icon={<Rows3 size={18} />} tone="slate" />
          <StatCard testId="kpi-fks" label="Foreign keys" value={o.counts.foreign_keys} icon={<GitFork size={18} />} tone="amber" hint={`${o.counts.inferred_relationships} conceptual (not enforced)`} />
          <StatCard testId="kpi-indexes" label="Indexes" value={o.counts.indexes} icon={<KeyRound size={18} />} tone="slate" hint={`${o.counts.rows} rows in total`} />
        </section>
      ) : !failed && <PanelSkeleton label="Loading database totals" />}
      {o?.demo_data_included && <p className="rounded-lg bg-purple-50 border border-purple-200 px-3 py-1.5 text-xs text-purple-800">Demonstration mode: row counts include clearly labelled synthetic complaints.</p>}

      <div role="tablist" aria-label="Database architecture sections" className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls={`panel-${k}`} data-testid={`tab-${k}`} onClick={() => choose(k)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold ${tab === k ? "bg-brand-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}>{label}</button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} data-testid={`panel-${tab}`}>
        <h2 className="sr-only">{TABS.find(([k]) => k === tab)?.[1]}</h2>
        {tab === "architecture" && (components.data ? <ArchitectureDiagram data={components.data} /> : components.error ? null : <PanelSkeleton label="Loading architecture" />)}

        {tab === "er" && (tables.data && rels.data && o ? (
          <div className="grid xl:grid-cols-[minmax(0,1fr)_440px] gap-6 items-start">
            <ErDiagram tables={tables.data.items} relationships={rels.data} schemas={o.schemas} selected={selected} onSelect={setSelected} />
            <aside className="card p-5 xl:sticky xl:top-4 max-h-[85vh] overflow-auto min-w-0" aria-label="Selected table" data-testid="er-detail-panel">
              {selected ? <TableDetail tableKey={selected} inferred={rels.data.inferred} onSelect={setSelected} />
                : <p className="text-sm text-slate-600">Select a table in the diagram to see its columns, constraints, indexes and relationships. Connected tables stay highlighted; the rest fade.</p>}
            </aside>
          </div>
        ) : failed ? null : <PanelSkeleton label="Loading ER diagram" />)}

        {tab === "schema" && (o ? <RelationalSchemaPanel schemas={o.schemas} /> : failed ? null : <PanelSkeleton label="Loading" />)}

        {tab === "implementation" && (tables.data && rels.data && o ? (
          <ImplementationPanel tables={tables.data.items} schemas={o.schemas} selected={selected} onSelect={setSelected} inferred={rels.data.inferred} />
        ) : failed ? null : <PanelSkeleton label="Loading implementation" />)}

        {tab === "advanced" && <AdvancedPanel />}
      </div>
    </main>
  );
}
