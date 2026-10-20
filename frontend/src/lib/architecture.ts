/** Client for the Database Architecture Explorer API plus the pure layout/highlight helpers used by the diagrams. */
import { APIError, tokens } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const token = tokens.access;
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/v1/architecture${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new APIError(0, "NETWORK_ERROR", "network");
  }
  if (!res.ok) throw new APIError(res.status, "API_ERROR", "request failed");
  return res.json();
}

export const architectureApi = {
  overview: () => get<any>("/overview"),
  components: () => get<any>("/components"),
  tables: () => get<any>("/tables"),
  table: (key: string) => { const [s, t] = key.split("."); return get<any>(`/tables/${encodeURIComponent(s)}/${encodeURIComponent(t)}`); },
  relationships: () => get<any>("/relationships"),
  schema: () => get<any>("/schema"),
  normalization: () => get<any>("/normalization"),
  advanced: () => get<any>("/advanced"),
  implementation: () => get<any>("/implementation"),
  runExample: (id: string) => get<any>(`/examples/${id}/run`),
  explainExample: (id: string) => get<any>(`/examples/${id}/explain`),
};

/** `label` is a translation key (st.*). */
export const STATUS_STYLE: Record<string, { cls: string; label: "st.active" | "st.unavailable" | "st.disabled" | "st.not installed" | "st.unknown" }> = {
  active: { cls: "badge-green", label: "st.active" },
  unavailable: { cls: "badge-red", label: "st.unavailable" },
  disabled: { cls: "badge-slate", label: "st.disabled" },
  "not installed": { cls: "badge-slate", label: "st.not installed" },
  unknown: { cls: "badge-slate", label: "st.unknown" },
};

export interface Positioned { key: string; x: number; y: number; w: number; h: number }

export const NODE_WIDTH = 250;
const HEADER = 44;
const ROW = 20;

/** Columns shown inside a node: every primary/foreign key plus up to three other columns. */
export function visibleColumns(t: any, compact: boolean): { shown: any[]; hidden: number } {
  if (compact) return { shown: [], hidden: t.columns.length };
  const keys = t.columns.filter((c: any) => c.pk || c.fk);
  const rest = t.columns.filter((c: any) => !c.pk && !c.fk).slice(0, 3);
  const shown = t.columns.filter((c: any) => keys.includes(c) || rest.includes(c));
  return { shown, hidden: t.columns.length - shown.length };
}

export function nodeHeight(t: any, compact: boolean): number {
  const { shown, hidden } = visibleColumns(t, compact);
  return HEADER + shown.length * ROW + (hidden && !compact ? ROW : 0) + (compact ? 14 : 12);
}

/** Domain-grouped layout: tables of one schema form a block; blocks flow left to right and wrap. Deterministic. */
export function layoutTables(tables: any[], schemaOrder: string[], compact: boolean, maxRowWidth = 2700): { positions: Record<string, Positioned>; labels: { schema: string; x: number; y: number; w: number }[] } {
  const bySchema = new Map<string, any[]>();
  for (const t of tables) bySchema.set(t.schema, [...(bySchema.get(t.schema) ?? []), t]);
  const order = [...schemaOrder.filter((s) => bySchema.has(s)), ...[...bySchema.keys()].filter((s) => !schemaOrder.includes(s))];
  const positions: Record<string, Positioned> = {};
  const labels: { schema: string; x: number; y: number; w: number }[] = [];
  const GAP_X = 50, GAP_Y = 24, BLOCK_GAP = 90, MAX_ROW_WIDTH = maxRowWidth, LABEL_H = 46;
  let cursorX = 0, cursorY = 0, rowHeight = 0;
  for (const schema of order) {
    const group = bySchema.get(schema)!.slice().sort((a, b) => a.name.localeCompare(b.name));
    const cols = Math.min(3, Math.max(1, Math.ceil(Math.sqrt(group.length))));
    const blockW = cols * NODE_WIDTH + (cols - 1) * GAP_X;
    if (cursorX > 0 && cursorX + blockW > MAX_ROW_WIDTH) { cursorX = 0; cursorY += rowHeight + BLOCK_GAP; rowHeight = 0; }
    labels.push({ schema, x: cursorX, y: cursorY, w: blockW });
    const colY = Array(cols).fill(cursorY + LABEL_H);
    for (const t of group) {
      const c = colY.indexOf(Math.min(...colY));
      const h = nodeHeight(t, compact);
      positions[t.key] = { key: t.key, x: cursorX + c * (NODE_WIDTH + GAP_X), y: colY[c], w: NODE_WIDTH, h };
      colY[c] += h + GAP_Y;
    }
    rowHeight = Math.max(rowHeight, Math.max(...colY) - cursorY);
    cursorX += blockW + BLOCK_GAP;
  }
  return { positions, labels };
}

/** Tables directly connected (either direction) to `key` through the given relationships. */
export function neighbours(key: string | null, rels: { from_table: string; to_table: string }[]): { tables: Set<string>; edges: Set<number> } {
  const tables = new Set<string>(), edges = new Set<number>();
  if (!key) return { tables, edges };
  tables.add(key);
  rels.forEach((r, i) => {
    if (r.from_table === key || r.to_table === key) { tables.add(r.from_table); tables.add(r.to_table); edges.add(i); }
  });
  return { tables, edges };
}

export const shortCardinality = (n: string) => n.replace(/\s/g, "").replace("..", "…");

/** Case-insensitive match on schema, table or column name. */
export function matchesTable(t: any, q: string): boolean {
  const s = q.trim().toLowerCase();
  return !s || t.key.toLowerCase().includes(s) || t.columns.some((c: any) => c.name.toLowerCase().includes(s));
}
