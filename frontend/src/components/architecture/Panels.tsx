"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Database, FileCode2, Play, Search } from "lucide-react";
import { architectureApi, matchesTable } from "@/lib/architecture";
import { EmptyState, ErrorState } from "@/components/ui/AsyncState";
import { TableDetail } from "@/components/architecture/TableDetail";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const run = useCallback(() => { setData(null); setError(""); fn().then(setData).catch((e) => setError(e.message)); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, reload: run };
}

export function PanelSkeleton({ label }: { label: string }) {
  return (
    <div className="space-y-3" role="status" aria-label={label} data-testid="panel-skeleton">
      {[0, 1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-6" style={{ width: `${95 - i * 9}%` }} />)}
    </div>
  );
}

/* ───────────────────────── Relational schema + normalization ───────────────────────── */
export function RelationalSchemaPanel({ schemas }: { schemas: any[] }) {
  const rel = useAsync(() => architectureApi.schema());
  const norm = useAsync(() => architectureApi.normalization());
  const fks = useAsync(() => architectureApi.relationships());
  const [q, setQ] = useState("");
  const [schema, setSchema] = useState("");
  const rows = useMemo(() => (rel.data?.relations ?? []).filter((r: any) =>
    (!schema || r.table.startsWith(schema + ".")) && (!q.trim() || r.table.toLowerCase().includes(q.trim().toLowerCase()) || r.notation.toLowerCase().includes(q.trim().toLowerCase()))), [rel.data, q, schema]);
  const onDelete = useMemo(() => {
    const m: Record<string, number> = {};
    (fks.data?.foreign_keys ?? []).forEach((f: any) => { m[f.on_delete] = (m[f.on_delete] || 0) + 1; });
    return m;
  }, [fks.data]);

  return (
    <div className="space-y-8" data-testid="relational-panel">
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-slate-900">Relational schema</h2>
        <p className="text-sm text-slate-600 max-w-3xl">
          Each relation is written <span className="font-mono">TABLE(attribute, …)</span>. <b>PK:</b> primary key, <b>FK:</b> foreign key. Referential integrity is enforced by the database:
          a row can only reference an existing parent row
          {Object.keys(onDelete).length > 0 && <> (delete rules in use: {Object.entries(onDelete).map(([k, v]) => `${k} × ${v}`).join(", ")})</>}.
        </p>
        <div className="flex flex-wrap gap-2 items-center">
          <label className="relative"><span className="sr-only">Filter relations</span><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden />
            <input className="input pl-9 py-1.5 w-64" placeholder="Filter relations…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="relational-search" /></label>
          <select aria-label="Schema" className="input w-auto py-1.5" value={schema} onChange={(e) => setSchema(e.target.value)}>
            <option value="">All schemas</option>{schemas.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
          <span className="text-xs text-slate-500" aria-live="polite" data-testid="relational-count">{rel.data ? `${rows.length} of ${rel.data.total} relations` : ""}</span>
        </div>
        {rel.error && <ErrorState message={rel.error} onRetry={rel.reload} />}
        {!rel.error && !rel.data && <PanelSkeleton label="Loading relational schema" />}
        {rel.data && rows.length === 0 && <EmptyState message="No relation matches the filter." />}
        {rows.length > 0 && (
          <ul className="space-y-3" data-testid="relation-list">
            {rows.map((r: any) => (
              <li key={r.table} className="card p-4" data-relation={r.table}>
                <p className="font-mono text-sm break-words text-slate-900">{r.notation}</p>
                <p className="text-xs text-slate-500 mt-1 font-mono">{r.table}</p>
                <div className="mt-2 grid sm:grid-cols-2 gap-x-6 gap-y-1 text-xs text-slate-700">
                  <p><b>Primary key:</b> {r.primary_key.join(", ") || "none"}</p>
                  {r.unique.length > 0 && <p><b>Unique:</b> {r.unique.map((u: string[]) => u.join("+")).join("; ")}</p>}
                  {r.foreign_keys.map((f: any) => <p key={f.columns.join()}><b>FK</b> {f.columns.join(", ")} → <span className="font-mono">{f.references}</span> <span className="text-slate-500">(ON DELETE {f.on_delete})</span></p>)}
                  {r.not_null.length > 0 && <p className="sm:col-span-2"><b>Not null:</b> {r.not_null.join(", ")}</p>}
                  {r.checks.map((c: string) => <p key={c} className="sm:col-span-2 font-mono break-all"><b className="font-sans">Check:</b> {c}</p>)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3" data-testid="normalization">
        <h2 className="text-lg font-bold text-slate-900">Normalization</h2>
        {norm.error && <ErrorState message={norm.error} onRetry={norm.reload} />}
        {!norm.error && !norm.data && <PanelSkeleton label="Loading normalization analysis" />}
        {norm.data && (
          <>
            <ul className="text-sm text-slate-700 list-disc pl-5 space-y-1 max-w-3xl">{norm.data.notes.map((n: string) => <li key={n}>{n}</li>)}</ul>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-center">
              {[["Tables analysed", norm.data.summary.tables], ["Without primary key", norm.data.summary.without_primary_key], ["Composite candidate key", norm.data.summary.with_composite_candidate_key],
                ["JSON/array columns to review", norm.data.summary.with_non_atomic_candidates], ["Possible redundancy hints", norm.data.summary.with_possible_redundancy]].map(([l, v]) => (
                <div key={String(l)} className="card p-3"><p className="text-2xl font-black text-slate-900">{v}</p><p className="text-xs text-slate-600">{l}</p></div>))}
            </div>
            <div className="card overflow-x-auto">
              <table className="data-table text-xs" data-testid="normalization-table">
                <thead><tr><th>Table</th><th>1NF</th><th>2NF</th><th>3NF</th><th>Recommendations to review</th></tr></thead>
                <tbody>
                  {norm.data.tables.filter((t: any) => t.possible_redundancy.length || t.composite_candidate_keys.length || t.non_atomic_candidates.length).map((t: any) => (
                    <tr key={t.table}>
                      <td className="font-mono whitespace-nowrap">{t.table}</td><td className="max-w-[16rem]">{t.first_nf}</td><td className="max-w-[16rem]">{t.second_nf}</td><td className="max-w-[14rem]">{t.third_nf}</td>
                      <td className="max-w-[18rem]">
                        {t.non_atomic_candidates.length > 0 && <p>JSON/array/tsvector: {t.non_atomic_candidates.join(", ")}</p>}
                        {t.possible_redundancy.map((r: any) => <p key={r.column}>Column <b className="font-mono">{r.column}</b> also exists in <span className="font-mono">{r.also_in}</span></p>)}
                      </td>
                    </tr>))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-600">Only tables with something to review are listed above; the remaining {norm.data.summary.tables - norm.data.tables.filter((t: any) => t.possible_redundancy.length || t.composite_candidate_keys.length || t.non_atomic_candidates.length).length} have a primary key, only single-column candidate keys, and scalar columns. Third normal form is deliberately not claimed for any table.</p>
          </>
        )}
      </section>
    </div>
  );
}

/* ───────────────────────── Implementation ───────────────────────── */
function ExampleCard({ ex }: { ex: any }) {
  const [res, setRes] = useState<any>(null);
  const [plan, setPlan] = useState<string[] | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (kind: "run" | "explain") => {
    setBusy(true); setErr("");
    try {
      if (kind === "run") setRes(await architectureApi.runExample(ex.id)); else setPlan((await architectureApi.explainExample(ex.id)).plan);
    } catch (e: any) { setErr(e.message); }
    setBusy(false);
  };
  return (
    <article className="card p-4 space-y-2" data-testid="example-card" data-example={ex.id}>
      <h3 className="font-bold text-slate-900">{ex.title}</h3>
      <p className="text-sm text-slate-700"><b>Purpose:</b> {ex.purpose}</p>
      <p className="text-xs text-slate-600"><b>Tables:</b> <span className="font-mono">{ex.tables.join(", ")}</span></p>
      {ex.relationships.length > 0 && <p className="text-xs text-slate-600"><b>Relationships followed:</b> <span className="font-mono">{ex.relationships.join("; ")}</span></p>}
      <p className="text-xs text-slate-600"><b>Result means:</b> {ex.result}</p>
      <pre className="rounded-lg bg-slate-900 text-slate-100 text-xs p-3 overflow-x-auto whitespace-pre-wrap">{ex.sql}</pre>
      <div className="flex gap-2">
        <button className="btn-primary py-1.5" disabled={busy} onClick={() => run("run")} data-testid="run-example"><Play size={14} /> Run (read-only)</button>
        <button className="btn-secondary py-1.5" disabled={busy} onClick={() => run("explain")} data-testid="explain-example">Query plan</button>
      </div>
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {res && (
        <div className="overflow-x-auto rounded-xl border border-slate-100" data-testid="example-result">
          <table className="data-table text-xs"><thead><tr>{res.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{res.rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j}>{v === null ? <span className="text-slate-500">NULL</span> : String(v)}</td>)}</tr>)}
              {res.rows.length === 0 && <tr><td colSpan={res.columns.length} className="text-slate-500">No rows.</td></tr>}</tbody></table>
          <p className="text-xs text-slate-500 p-2">{res.row_count} row(s).</p>
        </div>
      )}
      {plan && <pre className="rounded-lg bg-slate-50 border border-slate-200 text-xs p-3 overflow-x-auto" data-testid="example-plan">{plan.join("\n")}</pre>}
    </article>
  );
}

export function ImplementationPanel({ tables, schemas, selected, onSelect, inferred }: { tables: any[]; schemas: any[]; selected: string | null; onSelect: (k: string | null) => void; inferred: any[] }) {
  const impl = useAsync(() => architectureApi.implementation());
  const [q, setQ] = useState("");
  const [schema, setSchema] = useState("");
  const list = useMemo(() => tables.filter((t) => (!schema || t.schema === schema) && matchesTable(t, q)), [tables, q, schema]);
  return (
    <div className="space-y-8" data-testid="implementation-panel">
      <div className="grid lg:grid-cols-[320px_1fr] gap-6">
        <aside className="space-y-3">
          <label className="relative block"><span className="sr-only">Search tables</span><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden />
            <input className="input pl-9 py-1.5" placeholder="Search table or column…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="impl-search" /></label>
          <select aria-label="Schema filter" className="input py-1.5" value={schema} onChange={(e) => setSchema(e.target.value)}>
            <option value="">All schemas ({tables.length} tables)</option>{schemas.map((s) => <option key={s.name} value={s.name}>{s.name} ({s.tables})</option>)}
          </select>
          <p className="text-xs text-slate-500" aria-live="polite" data-testid="impl-count">{list.length} table(s)</p>
          <ul className="max-h-[560px] overflow-auto rounded-xl border border-slate-100 divide-y divide-slate-100 bg-white" data-testid="impl-table-list">
            {list.map((t) => (
              <li key={t.key}>
                <button onClick={() => onSelect(t.key)} aria-current={selected === t.key} data-table={t.key}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-50 ${selected === t.key ? "bg-brand-50 font-semibold" : ""}`}>
                  <span className="font-mono text-xs block truncate">{t.key}</span>
                  <span className="text-[11px] text-slate-500">{t.column_count} cols · {t.row_count ?? "?"} rows · {t.fk_count} FK</span>
                </button>
              </li>))}
            {list.length === 0 && <li className="p-4 text-sm text-slate-500">No table matches.</li>}
          </ul>
        </aside>
        <section className="card p-5 min-w-0" aria-label="Table details">
          {selected ? <TableDetail tableKey={selected} inferred={inferred} onSelect={onSelect} /> : <EmptyState message="Select a table to see its columns, constraints, indexes, relationships, example joins and sample rows." />}
        </section>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2"><FileCode2 size={18} aria-hidden /> Schema, migrations and seeds</h2>
        {impl.error && <ErrorState message={impl.error} onRetry={impl.reload} />}
        {!impl.error && !impl.data && <PanelSkeleton label="Loading implementation details" />}
        {impl.data && (
          <div className="grid md:grid-cols-3 gap-4 text-xs" data-testid="database-files">
            {([["Baseline schema", impl.data.files.schema], ["Migrations (applied in order)", impl.data.files.migrations], ["Seed scripts", impl.data.files.seeds]] as const).map(([title, files]) => (
              <div key={title} className="card p-4"><h3 className="font-semibold text-slate-800 mb-2">{title} ({files.length})</h3>
                <ul className="font-mono space-y-0.5">{files.map((f: any) => <li key={f.file}>{f.file.split("/").pop()} <span className="text-slate-500">· {(f.bytes / 1024).toFixed(1)} KB</span></li>)}{files.length === 0 && <li className="text-slate-500 font-sans">Not found in this deployment.</li>}</ul></div>))}
            <div className="md:col-span-3 card p-4"><h3 className="font-semibold text-slate-800 mb-1">Engine</h3>
              <p>{impl.data.engine}. Extensions: {Object.entries(impl.data.extensions).map(([k, v]) => `${k} ${v}`).join(", ") || "—"}.</p></div>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2"><Database size={18} aria-hidden /> Example queries (read-only)</h2>
        <p className="text-sm text-slate-600 max-w-3xl">Fixed queries written against the real schema. They run inside a read-only transaction with a short timeout; arbitrary SQL cannot be entered here.</p>
        {impl.data && <div className="grid xl:grid-cols-2 gap-4">{impl.data.examples.map((ex: any) => <ExampleCard key={ex.id} ex={ex} />)}</div>}
      </section>
    </div>
  );
}

/* ───────────────────────── Advanced concepts ───────────────────────── */
export function AdvancedPanel() {
  const adv = useAsync(() => architectureApi.advanced());
  if (adv.error) return <ErrorState message={adv.error} onRetry={adv.reload} />;
  if (!adv.data) return <PanelSkeleton label="Loading advanced concepts" />;
  return (
    <div className="space-y-4" data-testid="advanced-panel">
      <p className="text-sm text-slate-600 max-w-3xl">Only mechanisms that exist in this repository are shown as <b>Implemented</b>. Anything absent is labelled <b>Not implemented</b> and explained.</p>
      <div className="grid lg:grid-cols-2 gap-4">
        {adv.data.concepts.map((c: any) => (
          <article key={c.concept} className="card p-4 space-y-2" data-testid="concept-card" data-concept={c.concept} data-status={c.status}>
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-bold text-slate-900">{c.concept}</h3>
              <span className={`badge ${c.status === "Implemented" ? "badge-green" : "badge-slate"}`}>{c.status}</span>
            </div>
            <p className="text-sm text-slate-700">{c.summary}</p>
            <p className="text-xs text-slate-500">Location: <span className="font-mono break-words">{c.location}</span></p>
            {c.examples.length > 0 && (
              <details className="rounded-lg bg-slate-50 p-2">
                <summary className="cursor-pointer text-xs font-semibold text-slate-700">Show real examples ({c.examples.length})</summary>
                <ul className="mt-2 space-y-2 text-xs">
                  {c.examples.map((e: any, i: number) => (
                    <li key={i} className="rounded border border-slate-200 bg-white p-2">
                      {e.definition ? (<><p className="font-mono font-semibold">{e.schema ? `${e.schema}.` : ""}{e.name}{e.table ? ` on ${e.table}` : ""}{e.function ? ` → ${e.function}()` : ""}</p>
                        <pre className="mt-1 overflow-x-auto whitespace-pre-wrap text-[11px] text-slate-700 max-h-40">{e.definition}</pre></>)
                        : e.method ? (<><p className="font-semibold">{e.method}: {e.count} index(es)</p><ul className="font-mono text-[11px] text-slate-600">{e.examples.map((x: any) => <li key={x.index}>{x.table} · {x.index}</li>)}</ul></>)
                        : e.purpose ? (<p><span className="font-mono">{e.table}</span> — {e.rows ?? "?"} rows — {e.purpose}</p>)
                        : e.column ? (<p className="font-mono">{e.table}.{e.column} <span className="text-slate-500">({e.type})</span></p>)
                        : (<p className="font-mono">{Object.entries(e).map(([k, v]) => `${k}: ${v}`).join(", ")}</p>)}
                    </li>))}
                </ul>
              </details>
            )}
          </article>))}
      </div>
      <div className="card p-4 text-xs"><h3 className="font-semibold text-slate-800 mb-1">Installed extensions</h3><p className="font-mono">{adv.data.extensions.map((e: any) => `${e.name} ${e.version}`).join(" · ")}</p></div>
    </div>
  );
}
