import type { Filing, FinancialStatement, DriftAlert, PipelineMetrics, VolumePoint } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  metrics: () => get<PipelineMetrics>("/api/metrics"),

  filings: (opts?: { form?: string; limit?: number }) =>
    get<{ count: number; data: Filing[] }>(`/api/filings${qs({ form: opts?.form, limit: opts?.limit })}`),

  financials: (opts?: { company?: string; form_type?: string; limit?: number }) =>
    get<{ count: number; data: FinancialStatement[] }>(
      `/api/financials${qs({ company: opts?.company, form_type: opts?.form_type, limit: opts?.limit })}`
    ),

  drift: (opts?: { form?: string; limit?: number }) =>
    get<{ count: number; data: DriftAlert[] }>(`/api/drift${qs({ form: opts?.form, limit: opts?.limit })}`),

  volume: (days?: number) =>
    get<{ days: number; data: VolumePoint[] }>(`/api/volume${qs({ days })}`),
};
