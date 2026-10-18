/**
 * MyGovt API Client — typed wrapper around all backend endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class APIError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }));
    throw new APIError(res.status, error.code || "API_ERROR", error.message || error.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────
export const auth = {
  login: (email: string, password: string) =>
    request<{ access_token: string; refresh_token: string; user: any }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (email: string, password: string, full_name: string) =>
    request("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password, full_name }) }),
  me: () => request<any>("/api/v1/auth/me"),
  logout: () => request("/api/v1/auth/logout", { method: "POST" }),
};

// ── Schemes ───────────────────────────────────────────────────
export const schemes = {
  list: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
    );
    return request<any>(`/api/v1/schemes?${q}`);
  },
  get: (id: string) => request<any>(`/api/v1/schemes/${id}`),
  checkEligibility: (id: string, profile: any) =>
    request<any>(`/api/v1/schemes/${id}/eligibility`, { method: "POST", body: JSON.stringify(profile) }),
  categories: () => request<string[]>("/api/v1/schemes/categories/list"),
};

// ── Services ──────────────────────────────────────────────────
export const services = {
  list: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
    );
    return request<any>(`/api/v1/services?${q}`);
  },
  get: (id: string) => request<any>(`/api/v1/services/${id}`),
};

// ── Documents ─────────────────────────────────────────────────
export const documents = {
  list: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
    );
    return request<any>(`/api/v1/documents?${q}`);
  },
  get: (id: string) => request<any>(`/api/v1/documents/${id}`),
  search: (q: string, doc_type?: string) =>
    request<any>(`/api/v1/documents/search/full-text?q=${encodeURIComponent(q)}${doc_type ? `&doc_type=${doc_type}` : ""}`),
};

// ── Complaints ────────────────────────────────────────────────
export const complaints = {
  submit: (data: any) => request<any>("/api/v1/complaints", { method: "POST", body: JSON.stringify(data) }),
  track: (reference: string) => request<any>(`/api/v1/complaints/track/${reference}`),
  mine: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
    );
    return request<any>(`/api/v1/complaints/mine?${q}`);
  },
  get: (id: string) => request<any>(`/api/v1/complaints/${id}`),
  categories: () => request<any[]>("/api/v1/complaints/categories/list"),
};

// ── Chat ──────────────────────────────────────────────────────
export const chat = {
  send: (message: string, conversation_id?: string) =>
    request<any>("/api/v1/chat/message", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id }),
    }),
  conversations: () => request<any[]>("/api/v1/chat/conversations"),
  messages: (id: string) => request<any[]>(`/api/v1/chat/conversations/${id}`),
  lineage: (id: string) => request<any>(`/api/v1/chat/decisions/${id}/lineage`),
};

// ── GIS ───────────────────────────────────────────────────────
export const gis = {
  resolve: (lat: number, lon: number) => request<any>(`/api/v1/gis/resolve-jurisdiction?lat=${lat}&lon=${lon}`),
  districts: () => request<any[]>("/api/v1/gis/districts"),
};

// ── Departments ───────────────────────────────────────────────
export const departments = {
  list: () => request<any[]>("/api/v1/departments"),
};

// ── Admin ─────────────────────────────────────────────────────
export const admin = {
  health: () => request<any>("/api/v1/admin/health"),
  overview: () => request<any>("/api/v1/admin/overview"),
  schemas: () => request<any[]>("/api/v1/admin/schemas"),
  tables: (schema: string) => request<any[]>(`/api/v1/admin/schemas/${schema}/tables`),
  tableDetail: (schema: string, table: string) => request<any>(`/api/v1/admin/schemas/${schema}/tables/${table}`),
  tableSample: (schema: string, table: string, limit = 20, offset = 0) =>
    request<any>(`/api/v1/admin/schemas/${schema}/tables/${table}/sample?limit=${limit}&offset=${offset}`),
  relationships: (schema?: string) =>
    request<any[]>(`/api/v1/admin/relationships${schema ? `?schema_name=${schema}` : ""}`),
  query: (sql: string) => request<any>("/api/v1/admin/query", { method: "POST", body: JSON.stringify({ sql }) }),
  datasets: () => request<any[]>("/api/v1/admin/datasets"),
  sources: () => request<any[]>("/api/v1/admin/sources"),
  auditLogs: (limit = 50, offset = 0) => request<any>(`/api/v1/admin/audit-logs?limit=${limit}&offset=${offset}`),
  kgStats: () => request<any>("/api/v1/admin/knowledge-graph/stats"),
  dataQuality: () => request<any>("/api/v1/admin/data-quality"),
  connections: () => request<any>("/api/v1/admin/databases/connections"),
};

// ── System ────────────────────────────────────────────────────
export const system = {
  health: () => request<any>("/health"),
};
