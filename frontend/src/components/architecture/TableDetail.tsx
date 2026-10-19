"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Key, Link2, Table2 } from "lucide-react";
import { architectureApi, shortCardinality } from "@/lib/architecture";
import { ErrorState } from "@/components/ui/AsyncState";

function Skeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading table details" data-testid="detail-skeleton">
      {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-5" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

function Badge({ children, cls = "badge-slate", title }: { children: React.ReactNode; cls?: string; title?: string }) {
  return <span className={`badge ${cls}`} title={title}>{children}</span>;
}

/** Everything the database knows about one table, plus its real relationships and example joins. */
export function TableDetail({ tableKey, inferred = [], onSelect }: { tableKey: string; inferred?: any[]; onSelect: (key: string) => void }) {
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setD(null); setError("");
    architectureApi.table(tableKey).then(setD).catch((e) => setError(e.message));
  }, [tableKey]);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!d) return <Skeleton />;
  const link = (key: string) => (
    <button className="underline text-brand-700 font-mono text-xs" onClick={() => onSelect(key)} data-testid="related-table">{key}</button>
  );
  const mine = inferred.filter((r) => r.from_table === d.key || r.to_table === d.key);

  return (
    <div className="space-y-5 text-sm" data-testid="table-detail" data-table={d.key}>
      <header>
        <p className="text-xs text-slate-500 flex items-center gap-1"><Table2 size={12} aria-hidden /> {d.domain}</p>
        <h3 className="text-lg font-bold text-slate-900 font-mono break-all" data-testid="detail-title">{d.key}</h3>
        <p className="text-xs text-slate-500">{d.column_count} columns · {d.row_count ?? "?"} rows · {d.index_count} indexes · {d.fk_count} foreign key(s) out, {d.referenced_by_count} in</p>
        {d.comment && <p className="mt-1 text-slate-600">{d.comment}</p>}
      </header>

      <section aria-label="Columns">
        <h4 className="font-semibold text-slate-800 mb-2">Columns</h4>
        <div className="overflow-x-auto rounded-xl border border-slate-100">
          <table className="data-table text-xs" data-testid="columns-table">
            <thead><tr><th>Column</th><th>Type</th><th>Constraints</th><th>Default</th></tr></thead>
            <tbody>
              {d.columns.map((c: any) => (
                <tr key={c.name} data-testid="column-row">
                  <td className="font-mono whitespace-nowrap">{c.name}</td>
                  <td className="font-mono text-slate-600">{c.type}</td>
                  <td>
                    <span className="flex flex-wrap gap-1">
                      {c.pk && <Badge cls="badge-yellow" title="Primary key"><Key size={10} className="mr-0.5" aria-hidden />PK</Badge>}
                      {c.fk && <Badge cls="badge-blue" title={`References ${c.references?.table}`}><Link2 size={10} className="mr-0.5" aria-hidden />FK</Badge>}
                      {c.unique && <Badge cls="badge-purple" title="Unique">UQ</Badge>}
                      {c.not_null && !c.pk && <Badge title="NOT NULL">NN</Badge>}
                    </span>
                    {c.references && <span className="text-slate-500"> → {link(c.references.table)}.{c.references.column}</span>}
                  </td>
                  <td className="font-mono text-slate-500 max-w-[12rem] truncate" title={c.default ?? ""}>{c.default ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-label="Relationships" className="grid sm:grid-cols-2 gap-4">
        <div>
          <h4 className="font-semibold text-slate-800 mb-2">References (enforced foreign keys)</h4>
          {d.references.length === 0 ? <p className="text-slate-500">None.</p> : (
            <ul className="space-y-2" data-testid="references-list">
              {d.references.map((r: any) => (
                <li key={r.constraint} className="rounded-lg bg-slate-50 p-2">
                  <p className="flex items-center gap-1 flex-wrap">{link(r.table)} <Badge cls="badge-blue" title={r.participation}>{shortCardinality(r.notation)}</Badge></p>
                  <p className="font-mono text-xs text-slate-500">{r.columns.join(", ")} <ArrowRight size={10} className="inline" aria-hidden /> {r.to_columns.join(", ")} · ON DELETE {r.on_delete}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="font-semibold text-slate-800 mb-2">Referenced by</h4>
          {d.referenced_by.length === 0 ? <p className="text-slate-500">No table references this one.</p> : (
            <ul className="space-y-2" data-testid="referenced-by-list">
              {d.referenced_by.map((r: any) => (
                <li key={r.constraint} className="rounded-lg bg-slate-50 p-2">
                  <p>{link(r.table)} <span className="text-xs text-slate-500">({r.cardinality.replace(/_/g, " ")})</span></p>
                  <p className="font-mono text-xs text-slate-500">{r.columns.join(", ")}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {mine.length > 0 && (
        <section aria-label="Conceptual relationships" className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-3" data-testid="inferred-section">
          <h4 className="font-semibold text-amber-900 mb-1">Conceptual relationships (not enforced)</h4>
          <p className="text-xs text-amber-800 mb-2">These columns look like references by name, but the database has no FOREIGN KEY for them.</p>
          <ul className="space-y-1 text-xs">{mine.map((r) => <li key={r.name} className="font-mono">{r.name}</li>)}</ul>
        </section>
      )}

      <section aria-label="Constraints and indexes">
        <h4 className="font-semibold text-slate-800 mb-2">Constraints</h4>
        <ul className="text-xs space-y-1">
          <li><b>Primary key:</b> <span className="font-mono">{d.primary_key.join(", ") || "none"}</span></li>
          {d.unique_constraints.map((u: any) => <li key={u.name}><b>Unique:</b> <span className="font-mono">{u.columns.join(", ")}</span> <span className="text-slate-500">({u.name})</span></li>)}
          {d.check_constraints.map((c: any) => <li key={c.name}><b>Check:</b> <span className="font-mono break-all">{c.definition}</span></li>)}
        </ul>
        <h4 className="font-semibold text-slate-800 mt-4 mb-2">Indexes ({d.indexes.length})</h4>
        <ul className="text-xs space-y-1" data-testid="index-list">
          {d.indexes.map((i: any) => (
            <li key={i.name} className="flex flex-wrap gap-1 items-center">
              <Badge cls={i.method === "btree" ? "badge-slate" : "badge-purple"}>{i.method}</Badge>
              {i.primary && <Badge cls="badge-yellow">primary</Badge>}{i.unique && !i.primary && <Badge cls="badge-blue">unique</Badge>}
              <span className="font-mono break-all">{i.name}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Used by the backend">
        <h4 className="font-semibold text-slate-800 mb-2">Backend source files that reference this table</h4>
        {d.used_in.length === 0 ? <p className="text-slate-500 text-xs">No backend source file mentions this table by name (it may only be touched by SQL files or triggers).</p> : (
          <ul className="text-xs font-mono space-y-0.5">{d.used_in.map((f: string) => <li key={f}>{f}</li>)}</ul>
        )}
      </section>

      {d.example_joins.length > 0 && (
        <section aria-label="Example joins">
          <h4 className="font-semibold text-slate-800 mb-2">Example joins</h4>
          <div className="space-y-2">
            {d.example_joins.map((j: any) => (
              <details key={j.relationship + j.direction} className="rounded-lg bg-slate-900 text-slate-100 p-2">
                <summary className="cursor-pointer text-xs">{j.direction} · {j.relationship}</summary>
                <pre className="text-xs overflow-x-auto mt-2 whitespace-pre-wrap">{j.sql}</pre>
              </details>
            ))}
          </div>
        </section>
      )}

      <section aria-label="Sample rows">
        <h4 className="font-semibold text-slate-800 mb-2">Sample rows</h4>
        {!d.sample.available ? (
          <p className="text-xs text-slate-500" data-testid="sample-unavailable">{d.sample.reason}</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-100">
              <table className="data-table text-xs" data-testid="sample-table">
                <thead><tr>{d.sample.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{d.sample.rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j} className="max-w-[14rem] truncate" title={String(v ?? "")}>{v === null ? <span className="text-slate-500">NULL</span> : String(v)}</td>)}</tr>)}</tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 mt-1">{d.sample.note}{d.sample.hidden_columns.length ? ` Hidden: ${d.sample.hidden_columns.join(", ")}.` : ""}</p>
          </>
        )}
      </section>
    </div>
  );
}
