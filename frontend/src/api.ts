export type MetricPoint = { dimensions: Record<string, string>; value: number }

export type MetricResult = {
  workspace: string
  metric: string
  label: string
  format: 'currency' | 'integer' | 'decimal'
  currency: string | null
  points: MetricPoint[]
  evidence: {
    evidence_id: string
    processing_run_id: number
    metric_definition: string
    scope: string
    row_count: number
  }
}

export type QualitySummary = {
  workspace: string
  processing_run_id: number
  raw_sales_records: number
  accepted_sales_records: number
  deduplicated_records: number
  quarantined_records: number
  repair_events: number
  refund_records: number
  acceptance_rate: number
}

export type AnalyticsQuery = {
  metric: string
  group_by?: string[]
  filters?: Record<string, string[]>
  date_from?: string
  date_to?: string
  date_grain?: 'day' | 'month'
  limit?: number
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const WORKSPACE = import.meta.env.VITE_WORKSPACE_SLUG ?? 'moneki'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null
    throw new Error(payload?.detail ?? `请求失败 (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function queryMetric(query: AnalyticsQuery, signal?: AbortSignal) {
  return request<MetricResult>(`/api/workspaces/${WORKSPACE}/analytics/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(query),
    signal,
  })
}

export function getQualitySummary(signal?: AbortSignal) {
  return request<QualitySummary>(`/api/workspaces/${WORKSPACE}/quality/summary`, { signal })
}
