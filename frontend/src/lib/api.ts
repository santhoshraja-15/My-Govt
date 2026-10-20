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

/** Token storage (localStorage). Access tokens are short-lived; the refresh token renews them. */
export const tokens = {
  get access() { return typeof window !== "undefined" ? localStorage.getItem("access_token") : null; },
  get refresh() { return typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null; },
  set(access: string, refresh?: string) {
    localStorage.setItem("access_token", access);
    if (refresh) localStorage.setItem("refresh_token", refresh);
  },
  clear() { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); },
};

/** FastAPI returns `detail` as a string or as a list of validation errors. */
function errorMessage(body: any, fallback: string): string {
  const d = body?.detail ?? body?.message;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((e: any) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
  return fallback;
}

let refreshing: Promise<boolean> | null = null;
async function refreshAccessToken(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;
  refreshing ??= fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }),
  }).then(async (r) => {
    if (!r.ok) return false;
    tokens.set((await r.json()).access_token);
    return true;
  }).catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

async function request<T>(path: string, options: RequestInit = {}, retried = false): Promise<T> {
  const token = tokens.access;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new APIError(0, "NETWORK_ERROR", "Cannot reach the server. Please check your connection and try again.");
  }

  if (res.status === 401 && !retried && !path.startsWith("/api/v1/auth/") && (await refreshAccessToken())) {
    return request<T>(path, options, true);
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new APIError(res.status, error.code || "API_ERROR", errorMessage(error, res.statusText || "Request failed"));
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
    request<any>("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password, full_name }) }),
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
  categories: () => request<string[]>("/api/v1/services/categories/list"),
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
  /** Official policy-document catalogue (Government Orders, policies, circulars, notifications, Acts). */
  policy: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== "").map(([k, v]) => [k, String(v)]));
    return request<any>(`/api/v1/documents/policy?${q}`);
  },
  search: (q: string, doc_type?: string) =>
    request<any>(`/api/v1/documents/search/full-text?q=${encodeURIComponent(q)}${doc_type ? `&doc_type=${doc_type}` : ""}`),
};

// ── Complaints ────────────────────────────────────────────────
export const complaints = {
  submit: (data: any) => request<any>("/api/v1/complaints", { method: "POST", body: JSON.stringify(data) }),
  track: (reference: string) => request<any>(`/api/v1/complaints/track/${reference}`),
  updateStatus: (id: string, new_status: string, remarks?: string) =>
    request<any>(`/api/v1/complaints/${id}/status`, { method: "PATCH", body: JSON.stringify({ new_status, remarks }) }),
  mine: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
    );
    return request<any>(`/api/v1/complaints/mine?${q}`);
  },
  get: (id: string) => request<any>(`/api/v1/complaints/${id}`),
  categories: () => request<any[]>("/api/v1/complaints/categories/list"),
  /** Staff (officer / department admin / state admin): complaints within the caller's department. */
  staffList: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== false).map(([k, v]) => [k, String(v)]));
    return request<any>(`/api/v1/complaints/assigned?${q}`);
  },
  officers: () => request<any[]>("/api/v1/complaints/officers"),
  assign: (id: string, officer_id?: string, remarks?: string) =>
    request<any>(`/api/v1/complaints/${id}/assign`, { method: "POST", body: JSON.stringify({ officer_id, remarks }) }),
};

// ── Chat ──────────────────────────────────────────────────────
export const chat = {
  send: (message: string, conversation_id?: string, language?: "en" | "ta") =>
    request<any>("/api/v1/chat/message", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id, language }),
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
  complaints: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]));
    return request<any>(`/api/v1/admin/complaints?${q}`);
  },
  departmentPerformance: () => request<any[]>("/api/v1/admin/department-performance"),
  verificationQueue: () => request<any>("/api/v1/admin/verification-queue"),
  auditLogs: (limit = 50, offset = 0) => request<any>(`/api/v1/admin/audit-logs?limit=${limit}&offset=${offset}`),
  kgStats: () => request<any>("/api/v1/admin/knowledge-graph/stats"),
  dataQuality: () => request<any>("/api/v1/admin/data-quality"),
  connections: () => request<any>("/api/v1/admin/databases/connections"),
};

// ── Public stats ──────────────────────────────────────────────
export const publicNames = { get: () => request<{ departments: Record<string, string>; categories: Record<string, string>; districts: Record<string, string> }>("/api/v1/public/names") };

export const publicStats = {
  get: () => request<{ schemes: number; services: number; departments: number; districts: number; verified_schemes: number }>("/api/v1/public/stats"),
};

// ── System ────────────────────────────────────────────────────
export const system = {
  health: () => request<any>("/health"),
};
