import type { components } from "./generated-api";

export type Status = components["schemas"]["StatusView"];
export type Appearance = components["schemas"]["AppearanceView"];
export type Group = components["schemas"]["GroupView"];
export type Job = components["schemas"]["JobView"];
export type SavedImport = components["schemas"]["ImportView"];
export type WorkspaceSummary = components["schemas"]["WorkspaceSummary"];
export type Workspace = components["schemas"]["WorkspaceView"];
export type GroupUpdate = Partial<Pick<Group, "name" | "note" | "appearance_ids" | "reviewed">>;

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) { super(message); this.name = "ApiError"; }
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { method, credentials: "same-origin", cache: "no-store", headers: method === "GET" ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError("connection_failed", "The local app server could not be reached. Check that it is running, then retry.", 0);
  }
  const value = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = value?.detail ?? value;
    const message = Array.isArray(detail) ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join("; ") : detail?.message ?? `Request failed (HTTP ${response.status}).`;
    throw new ApiError(detail?.code ?? "request_failed", message, response.status);
  }
  return value as T;
}

const workspacePath = (id: string) => `/workspaces/${encodeURIComponent(id)}`;
export const api = {
  session: () => request<Status>("/session", "POST"),
  status: () => request<Status>("/status"),
  connect: (endpoint: string, token: string) => request<Status>("/connect", "POST", { endpoint, token }),
  disconnect: () => request<{ ok: boolean }>("/disconnect", "POST"),
  workspaces: () => request<WorkspaceSummary[]>("/workspaces"),
  workspace: (id: string) => request<Workspace>(workspacePath(id)),
  export: (body: { name: string; date?: string; source?: string; camera?: string }) => request<{ workspace_id: string; job_id: string }>("/exports", "POST", body),
  cluster: (id: string, threshold: number, min_cluster_size: number) => request<{ job_id: string }>(`${workspacePath(id)}/cluster`, "POST", { threshold, min_cluster_size }),
  control: (id: string, action: "pause" | "resume" | "cancel") => request<Job>(`/jobs/${encodeURIComponent(id)}/control`, "POST", { action }),
  createGroup: (id: string, body: Required<GroupUpdate>) => request<Group>(`${workspacePath(id)}/groups`, "POST", body),
  updateGroup: (id: string, group: string, body: GroupUpdate) => request<Group>(`${workspacePath(id)}/groups/${encodeURIComponent(group)}`, "PATCH", body),
  discardGroup: (id: string, group: string) => request<{ ok: boolean }>(`${workspacePath(id)}/groups/${encodeURIComponent(group)}`, "DELETE"),
  prepareImport: (id: string, reviewer: string) => request<SavedImport>(`${workspacePath(id)}/imports`, "POST", { reviewer }),
  submitImport: (id: string, importId: string) => request<SavedImport>(`${workspacePath(id)}/imports/${encodeURIComponent(importId)}/submit`, "POST"),
};

export function errorText(error: unknown) {
  return error instanceof ApiError ? `${error.message} (${error.code})` : error instanceof Error ? error.message : "Something went wrong. Please retry.";
}

export function downloadJson(value: unknown, filename: string) {
  const href = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a"); link.href = href; link.download = filename; link.click(); URL.revokeObjectURL(href);
}
