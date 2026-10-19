"use client";

import "@xyflow/react/dist/style.css";
import { memo, useMemo, useState } from "react";
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { STATUS_STYLE } from "@/lib/architecture";

const POSITIONS: Record<string, { x: number; y: number }> = {
  frontend: { x: 330, y: 0 }, api: { x: 330, y: 130 }, services: { x: 330, y: 270 }, postgresql: { x: 330, y: 450 },
  postgis: { x: -30, y: 640 }, pgvector: { x: 430, y: 640 }, neo4j: { x: 780, y: 450 }, redis: { x: 780, y: 190 }, minio: { x: 780, y: 320 },
};
const LAYER_COLOR: Record<string, string> = { client: "#2563eb", application: "#0f766e", data: "#7c3aed" };

const ComponentNode = memo(function ComponentNode({ data }: NodeProps) {
  const { c, selected } = data as any;
  const st = STATUS_STYLE[c.status] ?? STATUS_STYLE.unknown;
  return (
    <div className={`rounded-xl bg-white border-2 px-3 py-2 w-[230px] shadow-sm ${selected ? "shadow-lg" : ""}`}
      style={{ borderColor: selected ? "#1d4ed8" : LAYER_COLOR[c.layer] ?? "#64748b", borderStyle: c.role.startsWith("optional") ? "dashed" : "solid" }}
      data-testid="arch-node" data-component={c.id} data-status={c.status}>
      <Handle type="target" position={Position.Top} />
      <p className="font-bold text-sm text-slate-900 truncate" title={c.name}>{c.name}</p>
      <p className="text-[11px] text-slate-500 truncate">{c.role}</p>
      <span className={`badge ${st.cls} mt-1`}>{st.label}</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});
const NODE_TYPES = { component: ComponentNode };

function Detail({ c, byId, onSelect }: { c: any; byId: Record<string, any>; onSelect: (id: string) => void }) {
  const st = STATUS_STYLE[c.status] ?? STATUS_STYLE.unknown;
  return (
    <div className="card p-5 space-y-3 text-sm min-w-0 [overflow-wrap:anywhere]" data-testid="arch-detail" data-component={c.id}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-bold text-slate-900">{c.name}</h3>
        <span className={`badge ${st.cls}`}>{st.label}</span>
        <span className="badge badge-slate">{c.role}</span>
        {c.version && <span className="badge badge-blue">v{c.version}</span>}
      </div>
      <p className="text-slate-700">{c.purpose}</p>
      {c.note && <p className="text-xs text-slate-600">{c.note}</p>}
      <dl className="grid sm:grid-cols-2 gap-3 text-xs">
        <div><dt className="text-slate-500">Implementation</dt><dd className="font-mono break-words">{c.location}</dd></div>
        <div><dt className="text-slate-500">Connected to</dt>
          <dd className="flex flex-wrap gap-1">{c.connects_to.length ? c.connects_to.map((id: string) => (
            <button key={id} className="badge badge-blue hover:bg-brand-100" onClick={() => onSelect(id)}>{byId[id]?.name ?? id}</button>)) : "—"}</dd></div>
        {c.endpoints.length > 0 && <div><dt className="text-slate-500">Endpoints</dt><dd className="font-mono">{c.endpoints.join(", ")}</dd></div>}
        {c.columns && c.columns.length > 0 && <div><dt className="text-slate-500">Columns</dt><dd className="font-mono break-words">{c.columns.join(", ")}</dd></div>}
      </dl>
      {c.tables.length > 0 && c.id !== "postgresql" && (
        <div><p className="text-xs text-slate-500 mb-1">Tables involved</p><p className="flex flex-wrap gap-1">{c.tables.map((t: string) => <span key={t} className="badge badge-slate font-mono">{t}</span>)}</p></div>
      )}
      {c.id === "postgresql" && <p className="text-xs text-slate-600">{c.tables.length} tables — explore them in the ER Diagram and Implementation tabs. Installed extensions: {Object.entries(c.extensions ?? {}).map(([k, v]) => `${k} ${v}`).join(", ")}.</p>}
      {c.status === "unavailable" && <p className="rounded-lg bg-red-50 border border-red-200 p-2 text-xs text-red-800">This service did not answer its health check from the API. It is optional, so the platform keeps working without it.</p>}
      {c.status === "disabled" && <p className="rounded-lg bg-slate-50 border border-slate-200 p-2 text-xs text-slate-700">Switched off by configuration (feature flag).</p>}
    </div>
  );
}

function Inner({ data }: { data: any }) {
  const [selected, setSelected] = useState("postgresql");
  const byId = useMemo(() => Object.fromEntries(data.nodes.map((n: any) => [n.id, n])), [data]);
  const nodes: Node[] = useMemo(() => data.nodes.map((c: any) => ({ id: c.id, type: "component", position: POSITIONS[c.id] ?? { x: 0, y: 0 }, data: { c, selected: c.id === selected } })), [data, selected]);
  const edges: Edge[] = useMemo(() => data.edges.map((e: any, i: number) => {
    const hot = e.from === selected || e.to === selected;
    const color = e.kind === "primary" ? "#1d4ed8" : e.kind === "extension" ? "#7c3aed" : "#64748b";
    return { id: `e${i}`, source: e.from, target: e.to, label: e.label, type: "smoothstep", animated: hot,
      labelStyle: { fontSize: 11, fontWeight: 600, fill: "#1e293b" }, labelBgStyle: { fill: "#fff", fillOpacity: 0.95 }, labelBgPadding: [6, 3] as [number, number],
      style: { stroke: color, strokeWidth: hot ? 3 : 1.6, strokeDasharray: e.kind === "optional" ? "6 4" : undefined, opacity: hot || selected === "" ? 1 : 0.55 },
      markerEnd: { type: MarkerType.ArrowClosed, color } };
  }), [data, selected]);

  return (
    <div className="space-y-4" data-testid="architecture-diagram">
      <div className="rounded-2xl border border-slate-200 bg-slate-50 h-[560px] sm:h-[680px]">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView fitViewOptions={{ padding: 0.12 }} nodesDraggable nodesConnectable={false}
          onNodeClick={(_, n) => setSelected(n.id)} minZoom={0.3} maxZoom={1.6} proOptions={{ hideAttribution: false }}>
          <Background gap={24} color="#cbd5e1" /><Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="card p-3 text-xs flex flex-wrap gap-x-6 gap-y-2" data-testid="architecture-legend">
        <span className="font-semibold text-slate-700">Legend</span>
        {Object.entries(data.legend).map(([k, v]) => <span key={k}><b className="capitalize">{k}</b>: {String(v)}</span>)}
        <span>Dashed border = optional service · select any box for details</span>
      </div>
      <Detail c={byId[selected]} byId={byId} onSelect={setSelected} />
    </div>
  );
}

export function ArchitectureDiagram({ data }: { data: any }) {
  return <ReactFlowProvider><Inner data={data} /></ReactFlowProvider>;
}
