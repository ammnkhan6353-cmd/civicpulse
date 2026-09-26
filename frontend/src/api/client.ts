/**
 * Typed API client. Every type comes from schema.d.ts, which is GENERATED from the
 * backend's OpenAPI schema (npm run gen:api) and checked for drift in CI - so the
 * frontend cannot silently disagree with the backend about the shape of the data.
 *
 * All URLs are relative (/api/...). No backend address, and no secret, is ever
 * compiled into this bundle: anything in a browser bundle is public.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Category = Schemas["Category"];
export type Priority = Schemas["Priority"];
export type Status = Schemas["Status"];
export type Complaint = Schemas["ComplaintOut"];
export type ComplaintCreate = Schemas["ComplaintCreate"];
export type ComplaintPage = Schemas["ComplaintPage"];
export type Stats = Schemas["StatsOut"];
export type Providers = Schemas["ProvidersOut"];
export type FieldError = Schemas["FieldError"];

// The enum *values* (not rules about them) - used to build filter dropdowns.
export const CATEGORIES: Category[] = ["water", "electricity", "sanitation", "roads", "streetlights", "other"];
export const PRIORITIES: Priority[] = ["high", "normal", "low"];
export const STATUSES: Status[] = ["open", "in_progress", "resolved", "rejected"];

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly fieldErrors: FieldError[] = [],
    public readonly retryAfterSeconds?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function newRequestId(): string {
  return globalThis.crypto?.randomUUID?.().replace(/-/g, "") ?? String(Date.now());
}

async function request<T>(path: string, init: RequestInit = {}): Promise<{ data: T; headers: Headers }> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": newRequestId(),
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let body: { detail?: string; errors?: FieldError[] } = {};
    try {
      body = await response.json();
    } catch {
      /* non-JSON error body */
    }
    const retryAfter = response.headers.get("Retry-After");
    // Surface the SERVER's message verbatim (e.g. "Invalid transition: resolved → open").
    throw new ApiError(
      body.detail ?? `Request failed with status ${response.status}`,
      response.status,
      body.errors ?? [],
      retryAfter ? Number(retryAfter) : undefined,
    );
  }
  return { data: (await response.json()) as T, headers: response.headers };
}

export const api = {
  async createComplaint(payload: ComplaintCreate): Promise<Complaint> {
    return (await request<Complaint>("/api/complaints", { method: "POST", body: JSON.stringify(payload) })).data;
  },

  async listComplaints(params: {
    category?: Category | "";
    priority?: Priority | "";
    status?: Status | "";
    page: number;
    pageSize: number;
  }): Promise<ComplaintPage> {
    const query = new URLSearchParams({ page: String(params.page), page_size: String(params.pageSize) });
    if (params.category) query.set("category", params.category);
    if (params.priority) query.set("priority", params.priority);
    if (params.status) query.set("status", params.status);
    return (await request<ComplaintPage>(`/api/complaints?${query.toString()}`)).data;
  },

  async updateStatus(id: string, status: Status): Promise<Complaint> {
    return (
      await request<Complaint>(`/api/complaints/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      })
    ).data;
  },

  async getStats(): Promise<{ stats: Stats; cacheHit: boolean }> {
    const { data, headers } = await request<Stats>("/api/stats");
    return { stats: data, cacheHit: headers.get("X-Cache") === "HIT" };
  },

  async getProviders(): Promise<Providers> {
    return (await request<Providers>("/api/meta/providers")).data;
  },
};
