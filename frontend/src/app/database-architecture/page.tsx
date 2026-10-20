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
import { useLang } from "@/lib/i18n";
import { AdvancedPanel, ImplementationPanel, PanelSkeleton, RelationalSchemaPanel, useAsync } from "@/components/architecture/Panels";

const TABS = [
  ["architecture", "ar.tab.architecture"], ["er", "ar.tab.er"], ["schema", "ar.tab.schema"], ["implementation", "ar.tab.implementation"], ["advanced", "ar.tab.advanced"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function DatabaseArchitecturePage() {
  const { t, apiError } = useLang();
  const user = useGuard((r) => r === "state_admin" || r === "system_admin");
  const [tab, setTab] = useState<Tab>("architecture");
  const [selected, setSelected] = useState<string | null>(null);
  const ok = !!user;                               // no API calls until the guard has confirmed an administrator
  const overview = useAsync(() => architectureApi.overview(), [user?.user_id], ok);
  const components = useAsync(() => architectureApi.components(), [user?.user_id], ok);
  const tables = useAsync(() => architectureApi.tables(), [user?.user_id], ok);
  const rels = useAsync(() => architectureApi.relationships(), [user?.user_id], ok);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab") as Tab | null;
    if (q && TABS.some(([k]) => k === q)) setTab(q);
  }, []);
  const choose = (k: Tab) => { setTab(k); window.history.replaceState(null, "", `?tab=${k}`); };

  if (!user) return <LoadingState />;
  const o = overview.data;
  const failed = (overview.error || tables.error || rels.error || components.error) ? apiError(overview.error || tables.error || rels.error || components.error) : "";

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6" data-testid="database-architecture">
      <header className="rounded-3xl hero-gradient text-white p-6 sm:p-8">
        <p className="text-blue-100 text-sm flex items-center gap-2"><Database size={16} aria-hidden /> {t("ar.kicker")}</p>
        <h1 className="text-2xl sm:text-3xl font-black mt-1">{t("ar.title")}</h1>
        <p className="text-blue-100 mt-2 max-w-3xl text-sm">
          {t("ar.intro")}
        </p>
        {o && (
          <ul className="flex flex-wrap gap-2 mt-4" aria-label={t("ar.technologies")} data-testid="technology-list">
            {o.technologies.map((tech: any) => {
              const st = STATUS_STYLE[tech.status] ?? STATUS_STYLE.unknown;
              return <li key={tech.name} className={`badge ${st.cls} gap-1 max-w-full truncate`} title={`${tech.name} — ${tech.role}`} data-status={tech.status} data-i18n-skip>{tech.name} · {t(st.label)}</li>;
            })}
          </ul>
        )}
      </header>

      {failed && <ErrorState message={failed} onRetry={() => { overview.reload(); tables.reload(); rels.reload(); components.reload(); }} />}

      {o ? (
        <section aria-label={t("ar.totals")} className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4" data-testid="kpi-grid">
          <StatCard testId="kpi-engines" label={t("ar.k.engines")} value={o.counts.data_technologies} icon={<Boxes size={18} />} hint={t("ar.k.enginesHint")} />
          <StatCard testId="kpi-schemas" label={t("ar.k.schemas")} value={o.counts.schemas} icon={<Layers size={18} />} tone="green" />
          <StatCard testId="kpi-tables" label={t("ar.k.tables")} value={o.counts.tables} icon={<Table2 size={18} />} />
          <StatCard testId="kpi-columns" label={t("ar.k.columns")} value={o.counts.columns} icon={<Rows3 size={18} />} tone="slate" />
          <StatCard testId="kpi-fks" label={t("ar.k.fks")} value={o.counts.foreign_keys} icon={<GitFork size={18} />} tone="amber" hint={t("ar.k.fksHint", { n: o.counts.inferred_relationships })} />
          <StatCard testId="kpi-indexes" label={t("ar.k.indexes")} value={o.counts.indexes} icon={<KeyRound size={18} />} tone="slate" hint={t("ar.k.indexesHint", { n: o.counts.rows })} />
        </section>
      ) : !failed && <PanelSkeleton label={t("ar.loadingTotals")} />}
      {o?.demo_data_included && <p className="rounded-lg bg-purple-50 border border-purple-200 px-3 py-1.5 text-xs text-purple-800">{t("ar.demoRows")}</p>}

      <div role="tablist" aria-label={t("ar.tabs")} className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
        {TABS.map(([k, labelKey]) => (
          <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls={`panel-${k}`} data-testid={`tab-${k}`} onClick={() => choose(k)}
            className={`px-4 py-2 rounded-xl text-sm font-semibold ${tab === k ? "bg-brand-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}>{t(labelKey)}</button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} data-testid={`panel-${tab}`}>
        <h2 className="sr-only">{t(TABS.find(([k]) => k === tab)![1])}</h2>
        {tab === "architecture" && (components.data ? <ArchitectureDiagram data={components.data} /> : components.error ? null : <PanelSkeleton label={t("ar.loadingArch")} />)}

        {tab === "er" && (tables.data && rels.data && o ? (
          <div className="grid xl:grid-cols-[minmax(0,1fr)_440px] gap-6 items-start">
            <ErDiagram tables={tables.data.items} relationships={rels.data} schemas={o.schemas} selected={selected} onSelect={setSelected} />
            <aside className="card p-5 xl:sticky xl:top-4 max-h-[85vh] overflow-auto min-w-0" aria-label={t("ar.selectedTable")} data-testid="er-detail-panel">
              {selected ? <TableDetail tableKey={selected} inferred={rels.data.inferred} onSelect={setSelected} />
                : <p className="text-sm text-slate-600">{t("ar.selectHint")}</p>}
            </aside>
          </div>
        ) : failed ? null : <PanelSkeleton label={t("ar.loadingEr")} />)}

        {tab === "schema" && (o ? <RelationalSchemaPanel schemas={o.schemas} /> : failed ? null : <PanelSkeleton label={t("ar.loading")} />)}

        {tab === "implementation" && (tables.data && rels.data && o ? (
          <ImplementationPanel tables={tables.data.items} schemas={o.schemas} selected={selected} onSelect={setSelected} inferred={rels.data.inferred} />
        ) : failed ? null : <PanelSkeleton label={t("ar.loadingImpl")} />)}

        {tab === "advanced" && <AdvancedPanel />}
      </div>
    </main>
  );
}
