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

export type AnalysisContext = {
  intent: 'category_leader' | 'product_revenue' | 'aov_trend' | 'store_comparison'
  product: string | null
  date_from: string | null
  date_to: string | null
}

export type ChartTarget =
  | 'overview'
  | 'revenue_trend'
  | 'product_ranking'
  | 'category_contribution'
  | 'aov_trend'
  | 'store_comparison'

export type ChartAction = {
  title: string
  query: AnalyticsQuery
  target: ChartTarget
  highlight: string | null
}

export type ChatResponse = {
  status: 'answered' | 'unsupported'
  answer: string
  context: AnalysisContext | null
  citations: {
    evidence_id: string
    processing_run_id: number
    metric: string
    label: string
    value: number
    display_value: string
    dimensions: Record<string, string>
    scope: string
  }[]
  chart_action: ChartAction | null
}

export type InsightFeed = {
  workspace: string
  period: string
  insights: {
    kind: 'performance_pulse' | 'growth_driver' | 'daily_signal'
    tone: 'positive' | 'watch' | 'neutral'
    priority: 'high' | 'medium' | 'low'
    title: string
    narrative: string
    action: string
    impact_display: string
    target: 'revenue_trend' | 'product_ranking' | 'store_comparison'
    highlight: string | null
    evidence_ids: string[]
  }[]
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

export function askAssistant(
  question: string,
  context: AnalysisContext | null,
  signal?: AbortSignal,
) {
  return request<ChatResponse>(`/api/workspaces/${WORKSPACE}/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, context }),
    signal,
  })
}

export async function streamAssistant(
  question: string,
  context: AnalysisContext | null,
  onStatus: (message: string) => void,
  signal?: AbortSignal,
) {
  const response = await fetch(
    `${API_BASE_URL}/api/workspaces/${WORKSPACE}/assistant/chat/stream`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context }),
      signal,
    },
  )
  if (!response.ok || !response.body) {
    throw new Error(`请求失败 (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ChatResponse | null = null
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = block.match(/^event: (.+)$/m)?.[1]
      const data = block.match(/^data: (.+)$/m)?.[1]
      if (!event || !data) continue
      const payload = JSON.parse(data) as { message?: string } | ChatResponse
      if (event === 'status' && 'message' in payload && payload.message) onStatus(payload.message)
      if (event === 'error' && 'message' in payload) throw new Error(payload.message)
      if (event === 'result') result = payload as ChatResponse
    }
    if (done) break
  }
  if (!result) throw new Error('分析服务未返回结果')
  return result
}

export function getInsights(signal?: AbortSignal) {
  return request<InsightFeed>(`/api/workspaces/${WORKSPACE}/insights`, { signal })
}
