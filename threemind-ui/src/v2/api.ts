import { locale } from "./i18n";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T = any>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/api/v2${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
      response.status,
    );
  }
  return response.json();
}
export const post = <T = any>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const projectPath = (id: string) =>
  `/projects/${encodeURIComponent(id)}`;
export type Project = {
  id: string;
  name: string;
  role: string;
  created_at: string;
};
export type Metrics = {
  time_us: string;
  nodes: number;
  edges: number;
  activation: number;
  inhibition: number;
  mean_weight: number | null;
  mean_activation: number | null;
  active_fraction: number | null;
  saturated_fraction: number | null;
  edge_density: number | null;
  life: string;
  sequence: number;
};
export type Run = {
  id: string;
  name: string;
  description: string;
  tags: string[];
  archived_at: string | null;
  metadata_revision: number;
  status: string;
  life: string;
  revision: number;
  time_us: string;
  state_hash: string | null;
  origin_hash: string | null;
  metrics: Partial<Metrics>;
  spec: Record<string, any>;
  created_at: string;
  error: string | null;
  assessment?: { id: string; name: string } | null;
  ecology?: {
    campaign_id: string;
    name: string;
    individual: string;
    status: string;
    external_inputs: boolean;
  } | null;
};
export const statuses: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  paused: "已暂停",
  completed: "已完成",
  failed: "运行失败",
  cancelled: "已终止",
  dead: "活动已耗尽",
  blocked: "资源阻塞",
  pending: "待处理",
  leased: "处理中",
  done: "已完成",
  planned: "尚未执行",
  interrupted: "已中断",
  unknown: "执行状态待核查",
  active: "活跃",
};
export function timeLabel(us: string | number | undefined) {
  if (us == null) return "—";
  const n = Number(us) / 1e6;
  return Number.isFinite(n)
    ? `${n.toLocaleString(locale(), { maximumFractionDigits: 3 })} s`
    : String(us) + " μs";
}
export function numberLabel(n: number | null | undefined, digits = 2) {
  return n == null
    ? "—"
    : n.toLocaleString(locale(), { maximumFractionDigits: digits });
}
