"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Key, Link2, Table2 } from "lucide-react";
import { architectureApi, shortCardinality } from "@/lib/architecture";
import { ErrorState } from "@/components/ui/AsyncState";
import { useLang } from "@/lib/i18n";

function Skeleton() {
  const { t } = useLang();
  return (
    <div className="space-y-3" role="status" aria-label={t("td.loading")} data-testid="detail-skeleton">
      {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-5" style={{ width: `${90 - i * 12}%` }} />)}
    </div>
  );
}

function Badge({ children, cls = "badge-slate", title }: { children: React.ReactNode; cls?: string; title?: string }) {
  return <span className={`badge ${cls}`} title={title}>{children}</span>;
}

/** Everything the database knows about one table, plus its real relationships and example joins. */
export function TableDetail({ tableKey, inferred = [], onSelect }: { tableKey: string; inferred?: any[]; onSelect: (key: string) => void }) {
  const { t, apiError } = useLang();
  const tx = t;
  const [d, setD] = useState<any>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setD(null); setError("");
    architectureApi.table(tableKey).then(setD).catch((e) => setError(apiError(e)));
  }, [tableKey, apiError]);
  useEffect(() => { load(); }, [load]);

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!d) return <Skeleton />;
  const link = (key: string) => (
    <button className="underline text-brand-700 font-mono text-xs" onClick={() => onSelect(key)} data-testid="related-table">{key}</button>
  );
  const mine = inferred.filter((r) => r.from_table === d.key || r.to_table === d.key);

  return (
    <div className="space-y-5 text-sm min-w-0 [overflow-wrap:anywhere]" data-testid="table-detail" data-table={d.key}>
      <header>
        <p className="text-xs text-slate-500 flex items-center gap-1"><Table2 size={12} aria-hidden /> <span lang="en">{d.domain}</span></p>
        <h3 className="text-lg font-bold text-slate-900 font-mono break-all" data-testid="detail-title">{d.key}</h3>
        <p className="text-xs text-slate-500">{t("td.meta", { cols: d.column_count, rows: d.row_count ?? "?", idx: d.index_count, out: d.fk_count, inn: d.referenced_by_count })}</p>
        {d.comment && <p className="mt-1 text-slate-600" lang="en">{d.comment}</p>}
      </header>

      <section aria-label={t("td.columns")}>
        <h4 className="font-semibold text-slate-800 mb-2">{t("td.columns")}</h4>
        <div className="overflow-x-auto rounded-xl border border-slate-100">
          <table className="data-table text-xs" data-testid="columns-table">
            <thead><tr><th>{t("td.col.column")}</th><th>{t("td.col.type")}</th><th>{t("td.col.constraints")}</th><th>{t("td.col.default")}</th></tr></thead>
            <tbody>
              {d.columns.map((c: any) => (
                <tr key={c.name} data-testid="column-row">
                  <td className="font-mono whitespace-nowrap">{c.name}</td>
                  <td className="font-mono text-slate-600">{c.type}</td>
                  <td>
                    <span className="flex flex-wrap gap-1">
                      {c.pk && <Badge cls="badge-yellow" title={t("td.pkTitle")}><Key size={10} className="mr-0.5" aria-hidden />PK</Badge>}
                      {c.fk && <Badge cls="badge-blue" title={t("td.fkTitle", { table: c.references?.table ?? "" })}><Link2 size={10} className="mr-0.5" aria-hidden />FK</Badge>}
                      {c.unique && <Badge cls="badge-purple" title={t("td.unique")}>UQ</Badge>}
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

      <section aria-label={t("td.relationships")} className="grid sm:grid-cols-2 gap-4">
        <div>
          <h4 className="font-semibold text-slate-800 mb-2">{t("td.references")}</h4>
          {d.references.length === 0 ? <p className="text-slate-500">{t("td.none")}</p> : (
            <ul className="space-y-2" data-testid="references-list">
              {d.references.map((r: any) => (
                <li key={r.constraint} className="rounded-lg bg-slate-50 p-2">
                  <p className="flex items-center gap-1 flex-wrap">{link(r.table)} <Badge cls="badge-blue" title={r.participation === "mandatory" ? tx("er.part.mandatory") : tx("er.part.optional")}>{shortCardinality(r.notation)}</Badge></p>
                  <p className="font-mono text-xs text-slate-500">{r.columns.join(", ")} <ArrowRight size={10} className="inline" aria-hidden /> {r.to_columns.join(", ")} · ON DELETE {r.on_delete}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="font-semibold text-slate-800 mb-2">{t("td.referencedBy")}</h4>
          {d.referenced_by.length === 0 ? <p className="text-slate-500">{t("td.noRefs")}</p> : (
            <ul className="space-y-2" data-testid="referenced-by-list">
              {d.referenced_by.map((r: any) => (
                <li key={r.constraint} className="rounded-lg bg-slate-50 p-2">
                  <p>{link(r.table)} <span className="text-xs text-slate-500" lang="en">({r.cardinality.replace(/_/g, " ")})</span></p>
                  <p className="font-mono text-xs text-slate-500">{r.columns.join(", ")}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {mine.length > 0 && (
        <section aria-label={t("td.conceptual")} className="rounded-xl border border-dashed border-amber-300 bg-amber-50 p-3" data-testid="inferred-section">
          <h4 className="font-semibold text-amber-900 mb-1">{t("td.conceptual")}</h4>
          <p className="text-xs text-amber-800 mb-2">{t("td.conceptualNote")}</p>
          <ul className="space-y-1 text-xs">{mine.map((r) => <li key={r.name} className="font-mono">{r.name}</li>)}</ul>
        </section>
      )}

      <section aria-label={t("td.constraints")}>
        <h4 className="font-semibold text-slate-800 mb-2">{t("td.cons")}</h4>
        <ul className="text-xs space-y-1">
          <li><b>{t("td.primaryKey")}</b> <span className="font-mono">{d.primary_key.join(", ") || t("td.noneLower")}</span></li>
          {d.unique_constraints.map((u: any) => <li key={u.name}><b>{t("td.uniqueLabel")}</b> <span className="font-mono">{u.columns.join(", ")}</span> <span className="text-slate-500">({u.name})</span></li>)}
          {d.check_constraints.map((c: any) => <li key={c.name}><b>{t("td.checkLabel")}</b> <span className="font-mono break-all">{c.definition}</span></li>)}
        </ul>
        <h4 className="font-semibold text-slate-800 mt-4 mb-2">{t("td.indexes", { n: d.indexes.length })}</h4>
        <ul className="text-xs space-y-1" data-testid="index-list">
          {d.indexes.map((i: any) => (
            <li key={i.name} className="flex flex-wrap gap-1 items-center">
              <Badge cls={i.method === "btree" ? "badge-slate font-mono" : "badge-purple font-mono"}>{i.method}</Badge>
              {i.primary && <Badge cls="badge-yellow">{t("td.primary")}</Badge>}{i.unique && !i.primary && <Badge cls="badge-blue">{t("td.uniqueLower")}</Badge>}
              <span className="font-mono break-all">{i.name}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label={t("td.usedBy")}>
        <h4 className="font-semibold text-slate-800 mb-2">{t("td.usedBy")}</h4>
        {d.used_in.length === 0 ? <p className="text-slate-500 text-xs">{t("td.notUsed")}</p> : (
          <ul className="text-xs font-mono space-y-0.5">{d.used_in.map((f: string) => <li key={f}>{f}</li>)}</ul>
        )}
      </section>

      {d.example_joins.length > 0 && (
        <section aria-label={t("td.joins")}>
          <h4 className="font-semibold text-slate-800 mb-2">{t("td.joins")}</h4>
          <div className="space-y-2">
            {d.example_joins.map((j: any) => (
              <details key={j.relationship + j.direction} className="rounded-lg bg-slate-900 text-slate-100 p-2">
                <summary className="cursor-pointer text-xs" lang="en">{j.direction} · {j.relationship}</summary>
                <pre className="text-xs overflow-x-auto mt-2 whitespace-pre-wrap">{j.sql}</pre>
              </details>
            ))}
          </div>
        </section>
      )}

      <section aria-label={t("td.sample")}>
        <h4 className="font-semibold text-slate-800 mb-2">{t("td.sample")}</h4>
        {!d.sample.available ? (
          <p className="text-xs text-slate-500" data-testid="sample-unavailable" lang="en">{d.sample.reason}</p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-xl border border-slate-100">
              <table className="data-table text-xs" data-testid="sample-table">
                <thead><tr>{d.sample.columns.map((c: string) => <th key={c} className="font-mono">{c}</th>)}</tr></thead>
                <tbody>{d.sample.rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j} className="max-w-[14rem] truncate font-mono" title={String(v ?? "")}>{v === null ? <span className="text-slate-500">NULL</span> : String(v)}</td>)}</tr>)}</tbody>
              </table>
            </div>
            <p className="text-xs text-slate-500 mt-1"><span lang="en">{d.sample.note}</span>{d.sample.hidden_columns.length ? t("td.hidden", { cols: d.sample.hidden_columns.join(", ") }) : ""}</p>
          </>
        )}
      </section>
    </div>
  );
}
