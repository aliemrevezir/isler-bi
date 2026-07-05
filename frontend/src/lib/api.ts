import axios, { AxiosError } from "axios";

// ---- Veri sözleşmeleri ----
export type Role = "admin" | "analyst" | "viewer";

export interface User {
  id: number;
  username: string;
  full_name?: string;
  role: Role;
}

export interface AdminUser {
  id: number;
  username: string;
  full_name?: string;
  role: Role;
  is_active: boolean;
  created_at?: string;
}

export interface Kpi {
  key: string;
  label: string;
  value: number;
  format: "int" | "money" | "num" | "pct" | "text";
}

export interface ChartSpec {
  type: string;
  title: string;
  x: string[];
  series: {
    name: string;
    data: number[];
    type?: string;
    yAxisIndex?: number;
  }[];
}

export interface Column {
  key: string;
  label: string;
  format: string;
}

export interface DashResult {
  kpis: Kpi[];
  charts: ChartSpec[];
  table: { columns: Column[]; rows: Record<string, unknown>[] };
}

export interface FilterDef {
  key: string;
  label: string;
  type: "month" | "select" | "multiselect" | "toggle" | "text";
  default?: string;
  min?: string;
  max?: string;
  placeholder?: string;
  options?: { value: string; label: string }[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// Ingest
export interface IngestSource {
  source: string;
  kind: string;
  db: string;
  table: string;
  last_watermark: string | null;
  last_run_at: string | null;
  last_status: string | null;
  rows_last: number | null;
}

export interface IngestSourceProgress {
  source: string;
  status: "pending" | "running" | "done" | "error";
  rows: number;
  total: number | null;
  percent: number;
  detail: string;
}

export interface IngestProgress {
  sources: IngestSourceProgress[];
  current: string | null;
  overall_percent: number;
}

export interface IngestRun {
  id: number;
  sources: string[] | null;
  mode: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  rows_out: number | null;
  error: string | null;
  triggered_by: string | null;
  log?: string;
  progress?: IngestProgress | null;
  overall_percent?: number | null;
}

// Jobs
export interface Job {
  key: string;
  title: string;
  description?: string;
  schedule?: string;
  enabled: boolean;
  depends_on?: string[];
  created_by?: string;
  updated_at?: string;
}

export interface JobProgress {
  percent: number;
  message: string;
  step: number;
  total: number | null;
}

export interface JobRun {
  id: number;
  job_key: string;
  status: "pending" | "running" | "success" | "error";
  started_at: string | null;
  finished_at: string | null;
  rows_out: number | null;
  log?: string;
  error?: string;
  triggered_by?: string;
  progress?: JobProgress | null;
  percent?: number | null;
}

export interface VersionMeta {
  id: number;
  created_by?: string;
  created_at: string;
}

export interface VersionDetail {
  code: string;
  created_at: string;
  created_by?: string;
}

// Dashboards
export interface Dashboard {
  key: string;
  title: string;
  description?: string;
  created_by?: string;
  updated_at?: string;
}

export interface DashMeta {
  filter_schema: FilterDef[];
}

export interface DashTestResult {
  filter_schema: FilterDef[];
  result: DashResult;
}

// Tables introspection
export interface TableInfo {
  schema: string;
  table: string;
  columns: { name: string; type: string }[];
}

// ---- Axios instance ----
export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function errMsg(e: unknown): string {
  const ax = e as AxiosError<{ detail?: string | { msg?: string }[] }>;
  const detail = ax.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg!;
  if (ax.message) return ax.message;
  return "Bilinmeyen bir hata oluştu.";
}

// ---- API çağrıları ----
export const authApi = {
  login: (username: string, password: string) => {
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);
    return api.post<LoginResponse>("/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
  me: () => api.get<User>("/auth/me"),
};

export const usersApi = {
  list: () => api.get<AdminUser[]>("/users"),
  create: (body: {
    username: string;
    password: string;
    full_name?: string;
    role: Role;
  }) => api.post<AdminUser>("/users", body),
  update: (
    id: number,
    body: Partial<{ full_name: string; role: Role; is_active: boolean }>
  ) => api.patch<AdminUser>(`/users/${id}`, body),
  setPassword: (id: number, password: string) =>
    api.post(`/users/${id}/password`, { password }),
  remove: (id: number) => api.delete(`/users/${id}`),
};

export const ingestApi = {
  sources: () => api.get<IngestSource[]>("/ingest/sources"),
  run: (body: {
    sources: string[] | null;
    mode: "incremental" | "backfill";
    from_date?: string;
    to_date?: string;
  }) => api.post<{ task_id: string; status: string; mode: string }>("/ingest/run", body),
  runs: () => api.get<IngestRun[]>("/ingest/runs"),
  run_detail: (id: number) => api.get<IngestRun>(`/ingest/runs/${id}`),
};

export const jobsApi = {
  list: () => api.get<Job[]>("/jobs"),
  create: (body: {
    key: string;
    title: string;
    description?: string;
    code?: string;
    schedule?: string;
    depends_on?: string[];
  }) => api.post<Job>("/jobs", body),
  get: (key: string) => api.get<Job>(`/jobs/${key}`),
  patch: (key: string, body: Partial<Job>) => api.patch<Job>(`/jobs/${key}`, body),
  remove: (key: string) => api.delete(`/jobs/${key}`),
  getCode: (key: string) => api.get<{ code: string }>(`/jobs/${key}/code`),
  putCode: (key: string, code: string) =>
    api.put<{ code: string }>(`/jobs/${key}/code`, { code }),
  versions: (key: string) => api.get<VersionMeta[]>(`/jobs/${key}/versions`),
  version: (key: string, vid: number) =>
    api.get<VersionDetail>(`/jobs/${key}/versions/${vid}`),
  run: (key: string) => api.post<{ run_id: number; status: string }>(`/jobs/${key}/run`),
  runs: (key: string) => api.get<JobRun[]>(`/jobs/${key}/runs`),
  runDetail: (run_id: number) => api.get<JobRun>(`/jobs/runs/${run_id}`),
};

export const dashApi = {
  list: () => api.get<Dashboard[]>("/dashboards"),
  create: (body: { key: string; title: string; description?: string; code?: string }) =>
    api.post<Dashboard>("/dashboards", body),
  get: (key: string) => api.get<Dashboard>(`/dashboards/${key}`),
  remove: (key: string) => api.delete(`/dashboards/${key}`),
  getCode: (key: string) => api.get<{ code: string }>(`/dashboards/${key}/code`),
  putCode: (key: string, code: string) =>
    api.put<{ code: string }>(`/dashboards/${key}/code`, { code }),
  versions: (key: string) => api.get<VersionMeta[]>(`/dashboards/${key}/versions`),
  version: (key: string, vid: number) =>
    api.get<VersionDetail>(`/dashboards/${key}/versions/${vid}`),
  meta: (key: string) => api.get<DashMeta>(`/dashboards/${key}/meta`),
  run: (key: string, filters: Record<string, unknown>) =>
    api.post<DashResult>(`/dashboards/${key}/run`, { filters }),
  test: (key: string, code: string, filters: Record<string, unknown>) =>
    api.post<DashTestResult>(`/dashboards/${key}/test`, { code, filters }),
  export: (key: string, filters: Record<string, unknown>) =>
    api.post(`/dashboards/${key}/export`, { filters }, { responseType: "blob" }),
};

export const tablesApi = {
  list: () => api.get<TableInfo[]>("/tables"),
  preview: (table: string, limit = 20) =>
    api.get<{ rows: Record<string, unknown>[] }>("/tables/preview", {
      params: { table, limit },
    }),
};

export function downloadBlob(data: BlobPart, filename: string) {
  const url = URL.createObjectURL(new Blob([data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
