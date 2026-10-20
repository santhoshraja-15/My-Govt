"use client";

import "@xyflow/react/dist/style.css";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, ReactFlowProvider, useNodesState, useReactFlow,
  type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import { Key, Link2, Maximize2, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";
import { useLang } from "@/lib/i18n";
import { flowLabels } from "@/lib/flowLabels";
import { layoutTables, matchesTable, neighbours, shortCardinality, visibleColumns, NODE_WIDTH } from "@/lib/architecture";

const TableNode = memo(function TableNode({ data }: NodeProps) {
  const { t, compact, dim, selected, color } = data as any;
  const { t: tr } = useLang();
  const { shown, hidden } = visibleColumns(t, compact);
  return (
    <div
      className={`rounded-xl bg-white border-2 shadow-sm text-left transition-opacity ${selected ? "shadow-lg" : ""}`}
      style={{ width: NODE_WIDTH, borderColor: selected ? "#1d4ed8" : color, opacity: dim ? 0.28 : 1 }}
      data-testid="er-node" data-table={t.key} data-selected={selected ? "true" : "false"} data-dim={dim ? "true" : "false"}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      <div className="px-3 py-2 rounded-t-[10px] text-white" style={{ background: color }}>
        <p className="font-mono text-xs font-bold truncate" title={t.key}>{t.name}</p>
        <p className="text-[11px]"><span className="font-mono">{t.schema}</span> · {tr("er.cols", { cols: t.column_count, rows: t.row_count ?? "?" })}</p>
      </div>
      {!compact && (
        <ul className="px-2 py-1.5 space-y-0.5">
          {shown.map((c: any) => (
            <li key={c.name} className="flex items-center gap-1 text-[11px] leading-5">
              {c.pk ? <Key size={10} className="text-amber-600 shrink-0" aria-label={tr("er.pk")} /> : c.fk ? <Link2 size={10} className="text-blue-600 shrink-0" aria-label={tr("er.fk")} /> : <span className="w-[10px] shrink-0" />}
              <span className={`font-mono truncate ${c.pk ? "font-bold" : ""}`}>{c.name}</span>
              <span className="ml-auto text-slate-500 truncate max-w-[84px] font-mono">{c.type}</span>
            </li>
          ))}
          {hidden > 0 && <li className="text-[10px] text-slate-500 pl-4">{tr("er.moreCols", { n: hidden })}</li>}
        </ul>
      )}
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
});

const LabelNode = memo(function LabelNode({ data }: NodeProps) {
  const { label, color, w } = data as any;
  return (
    <div style={{ width: w }} className="pb-1 border-b-4" aria-hidden>
      <span className="text-sm font-bold" lang="en" style={{ color, borderColor: color }}>{label}</span>
    </div>
  );
});

const NODE_TYPES = { table: TableNode, domain: LabelNode };

interface Props {
  tables: any[]; relationships: any; schemas: any[]; selected: string | null; onSelect: (key: string | null) => void;
}

function Diagram({ tables, relationships, schemas, selected, onSelect }: Props) {
  const { t } = useLang();
  const flow = useReactFlow();
  const [search, setSearch] = useState("");
  const [active, setActive] = useState<Set<string>>(() => new Set(schemas.map((s) => s.name)));
  const [compact, setCompact] = useState(false);
  const [labels, setLabels] = useState(false);
  const [inferred, setInferred] = useState(false);
  const [focus, setFocus] = useState(false);
  const [version, setVersion] = useState(0);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const fitTimer = useRef<ReturnType<typeof setTimeout>>();

  // focus mode: only the selected table and the tables it is directly related to (schema/search filters are ignored)
  const focusSet = useMemo(() => {
    if (!focus || !selected) return null;
    const every = [...relationships.foreign_keys, ...relationships.many_to_many, ...(inferred ? relationships.inferred : [])];
    return neighbours(selected, every).tables;
  }, [focus, selected, relationships, inferred]);
  const visible = useMemo(() => tables.filter((t) => (focusSet
    ? focusSet.has(t.key)
    : active.has(t.schema) && (matchesTable(t, search) || t.key === selected))), [tables, active, search, selected, focusSet]);
  const visibleKeys = useMemo(() => new Set(visible.map((t) => t.key)), [visible]);
  const colorOf = useMemo(() => Object.fromEntries(schemas.map((s) => [s.name, s.color])), [schemas]);

  const rels = useMemo(() => {
    const all = [
      ...relationships.foreign_keys.map((r: any) => ({ ...r, id: `fk:${r.name}` })),
      ...relationships.many_to_many.map((r: any, i: number) => ({ ...r, id: `mm:${i}`, name: r.name })),
      ...(inferred ? relationships.inferred.map((r: any) => ({ ...r, id: `inf:${r.name}` })) : []),
    ];
    return all.filter((r: any) => visibleKeys.has(r.from_table) && visibleKeys.has(r.to_table));
  }, [relationships, inferred, visibleKeys]);

  const near = useMemo(() => neighbours(selected, rels), [selected, rels]);

  // structure: rebuilt when the visible set, density or layout version changes (user-dragged positions survive highlighting)
  const structureKey = `${[...visibleKeys].sort().join("|")}#${compact}#${version}#${focusSet ? "f" : "a"}`;
  useEffect(() => {
    const { positions, labels: heads } = layoutTables(visible, schemas.map((s) => s.name), compact, focusSet ? 1300 : 2700);
    const next: Node[] = [
      ...heads.map((h) => ({ id: `label:${h.schema}`, type: "domain", position: { x: h.x, y: h.y }, draggable: false, selectable: false, focusable: false,
        data: { label: `${schemas.find((s) => s.name === h.schema)?.domain ?? h.schema} (${h.schema})`, color: colorOf[h.schema] ?? "#64748b", w: h.w } })),
      ...visible.map((t) => ({ id: t.key, type: "table", position: { x: positions[t.key].x, y: positions[t.key].y },
        data: { t, compact, dim: false, selected: false, color: colorOf[t.schema] ?? "#64748b" } })),
    ];
    setNodes(next);
    clearTimeout(fitTimer.current);
    fitTimer.current = setTimeout(() => flow.fitView({ padding: 0.08, duration: 250 }), 60);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structureKey]);

  // highlighting: touches only node data
  useEffect(() => {
    setNodes((nds) => nds.map((n) => (n.type !== "table" ? n : { ...n, data: { ...n.data, selected: n.id === selected, dim: !!selected && !near.tables.has(n.id) } })));
  }, [selected, near, setNodes]);

  // zoom to the selected table and its neighbours so names and types are readable (the full diagram is wide)
  useEffect(() => {
    if (!selected || near.tables.size === 0) return;
    const t = setTimeout(() => flow.fitView({ nodes: [...near.tables].map((id) => ({ id })), padding: 0.25, maxZoom: 1, duration: 450 }), 90);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const edges: Edge[] = useMemo(() => rels.map((r: any, i: number) => {
    const hot = near.edges.has(i);
    const dimmed = !!selected && !hot;
    const kind = r.kind;
    const stroke = hot ? "#1d4ed8" : kind === "inferred" ? "#d97706" : kind === "junction" ? "#7c3aed" : "#94a3b8";
    return {
      id: r.id, source: r.from_table, target: r.to_table, type: "smoothstep",
      label: hot || labels ? (kind === "inferred" ? t("er.inferredLabel") : shortCardinality(r.notation)) : undefined,
      labelStyle: { fontSize: 10, fontWeight: 700, fill: "#1e293b" }, labelBgStyle: { fill: "#fff", fillOpacity: 0.9 }, labelBgPadding: [4, 2] as [number, number],
      animated: hot, interactionWidth: 14,
      style: { stroke, strokeWidth: hot ? 2.5 : 1.2, opacity: dimmed ? 0.12 : 1, strokeDasharray: kind === "inferred" ? "6 4" : kind === "junction" ? "2 4" : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
      data: { kind },
    };
  }), [rels, near, selected, labels, t]);

  const toggleSchema = (s: string) => setActive((prev) => { const n = new Set(prev); n.has(s) ? n.delete(s) : n.add(s); return n.size ? n : new Set(prev); });
  const matches = useMemo(() => (search.trim() ? tables.filter((t) => matchesTable(t, search)).slice(0, 10) : []), [tables, search]);
  const fit = useCallback(() => flow.fitView({ padding: 0.08, duration: 300 }), [flow]);

  return (
    <div className="space-y-3" data-testid="er-diagram">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative">
          <span className="sr-only">{t("er.searchSr")}</span>
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" aria-hidden />
          <input className="input pl-9 py-1.5 w-64" placeholder={t("er.searchPh")} value={search} onChange={(e) => setSearch(e.target.value)} data-testid="er-search" />
        </label>
        <button type="button" className="btn-secondary py-1.5" onClick={fit} data-testid="er-fit"><Maximize2 size={14} /> {t("er.fit")}</button>
        <button type="button" className="btn-secondary py-1.5" onClick={() => flow.zoomIn({ duration: 150 })} aria-label={t("er.zoomIn")}><ZoomIn size={14} /></button>
        <button type="button" className="btn-secondary py-1.5" onClick={() => flow.zoomOut({ duration: 150 })} aria-label={t("er.zoomOut")}><ZoomOut size={14} /></button>
        <button type="button" className="btn-secondary py-1.5" onClick={() => { setSearch(""); setActive(new Set(schemas.map((s) => s.name))); setVersion((v) => v + 1); onSelect(null); }} data-testid="er-reset">
          <RotateCcw size={14} /> {t("er.reset")}
        </button>
        <label className="flex items-center gap-1.5 text-sm text-slate-700" title={t("er.focusTitle")}>
          <input type="checkbox" checked={focus} onChange={(e) => setFocus(e.target.checked)} data-testid="er-focus" /> {t("er.focus")}</label>
        <label className="flex items-center gap-1.5 text-sm text-slate-700"><input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} data-testid="er-compact" /> {t("er.compact")}</label>
        <label className="flex items-center gap-1.5 text-sm text-slate-700"><input type="checkbox" checked={labels} onChange={(e) => setLabels(e.target.checked)} /> {t("er.cardinality")}</label>
        <label className="flex items-center gap-1.5 text-sm text-slate-700"><input type="checkbox" checked={inferred} onChange={(e) => setInferred(e.target.checked)} data-testid="er-inferred" /> {t("er.conceptual", { n: relationships.inferred.length })}</label>
      </div>

      <div role="group" aria-label={t("er.filterSchema")} className="flex flex-wrap gap-2">
        {schemas.map((s) => (
          <button key={s.name} type="button" aria-pressed={active.has(s.name)} onClick={() => toggleSchema(s.name)} data-testid={`schema-chip-${s.name}`}
            className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${active.has(s.name) ? "text-white" : "bg-white text-slate-500 border-slate-200"}`}
            style={active.has(s.name) ? { background: s.color, borderColor: s.color } : undefined}>
            <span className="font-mono">{s.name}</span> · {s.tables}
          </button>
        ))}
      </div>

      {matches.length > 0 && (
        <div className="flex flex-wrap gap-1.5" aria-label={t("er.matching")} data-testid="er-matches">
          {matches.map((m) => <button key={m.key} className="badge badge-blue hover:bg-brand-100" onClick={() => onSelect(m.key)}>{m.key}</button>)}
        </div>
      )}

      <p className="text-xs text-slate-600" data-testid="er-counts" aria-live="polite">
        {t("er.counts", { visible: visible.length, total: tables.length, rels: rels.length })}
        {selected ? t("er.countsSel", { sel: selected, n: near.tables.size - 1 }) : ""}.{focus && !selected ? t("er.selectToFocus") : ""}
      </p>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 h-[600px] sm:h-[72vh] sm:min-h-[640px] relative overflow-hidden">
        {visible.length === 0 && <p className="absolute inset-0 flex items-center justify-center text-slate-500" data-testid="er-empty">{t("er.empty")}</p>}
        <ReactFlow
          nodes={nodes} edges={edges} onNodesChange={onNodesChange} nodeTypes={NODE_TYPES}
          onNodeClick={(_, n) => { if (n.type === "table") onSelect(n.id); }} onPaneClick={() => onSelect(null)}
          minZoom={0.04} maxZoom={1.8} fitView proOptions={{ hideAttribution: false }} nodesFocusable edgesFocusable={false} ariaLabelConfig={flowLabels(t)}
        >
          <Background gap={24} color="#cbd5e1" />
          <Controls showInteractive={false} />
          <MiniMap pannable zoomable nodeColor={(n) => (n.type === "table" ? ((n.data as any).color as string) : "transparent")} ariaLabel={t("er.overview")} />
        </ReactFlow>
      </div>

      <div className="card p-3 text-xs flex flex-wrap gap-x-6 gap-y-2 items-center" aria-label={t("ar.legend")} data-testid="er-legend">
        <span className="font-semibold text-slate-700">{t("ar.legend")}</span>
        <span className="flex items-center gap-1"><Key size={12} className="text-amber-600" aria-hidden /> {t("er.pk")}</span>
        <span className="flex items-center gap-1"><Link2 size={12} className="text-blue-600" aria-hidden /> {t("er.fk")}</span>
        <span className="flex items-center gap-1"><svg width="34" height="8" aria-hidden><line x1="0" y1="4" x2="34" y2="4" stroke="#94a3b8" strokeWidth="2" /></svg> {t("er.legend.enforced")}</span>
        <span className="flex items-center gap-1"><svg width="34" height="8" aria-hidden><line x1="0" y1="4" x2="34" y2="4" stroke="#d97706" strokeWidth="2" strokeDasharray="6 4" /></svg> {t("er.legend.inferred")}</span>
        <span className="flex items-center gap-1"><svg width="34" height="8" aria-hidden><line x1="0" y1="4" x2="34" y2="4" stroke="#7c3aed" strokeWidth="2" strokeDasharray="2 4" /></svg> {t("er.legend.junction")}</span>
        <span><b>1 : 1..N</b> {t("er.legend.card")} · <b>1 : 0..N</b> {t("er.legend.cardOpt")} · <b>1 : 1</b> / <b>1 : 0..1</b> {t("er.legend.cardOne")}</span>
      </div>
    </div>
  );
}

export function ErDiagram(props: Props) {
  return <ReactFlowProvider><Diagram {...props} /></ReactFlowProvider>;
}
