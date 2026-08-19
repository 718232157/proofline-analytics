import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { AssistantDrawer } from './AssistantDrawer'
import {
  getQualitySummary,
  getInsights,
  queryMetric,
  type AnalyticsQuery,
  type MetricResult,
  type QualitySummary,
  type InsightFeed,
} from './api'

const TrendChart = lazy(() => import('./charts').then((module) => ({ default: module.TrendChart })))
const ProductsChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.ProductsChart })),
)

type DashboardData = {
  revenue: MetricResult
  orders: MetricResult
  aov: MetricResult
  trend: MetricResult
  products: MetricResult
  categories: MetricResult
  quality: QualitySummary
  insights: InsightFeed
}

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})
const integer = new Intl.NumberFormat('zh-CN')
const formatCurrency = (cents: number) => currency.format(cents / 100)

function App() {
  const [dateFrom, setDateFrom] = useState('2026-05-01')
  const [dateTo, setDateTo] = useState('2026-07-31')
  const dateFromRef = useRef<HTMLInputElement>(null)
  const dateToRef = useRef<HTMLInputElement>(null)
  const [appliedRange, setAppliedRange] = useState({ from: dateFrom, to: dateTo })
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [assistantOpen, setAssistantOpen] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    const scope = { date_from: appliedRange.from, date_to: appliedRange.to }
    setLoading(true)
    setError(null)
    Promise.all([
      queryMetric({ metric: 'revenue', ...scope }, controller.signal),
      queryMetric({ metric: 'order_count', ...scope }, controller.signal),
      queryMetric({ metric: 'average_order_value', ...scope }, controller.signal),
      queryMetric(
        { metric: 'revenue', group_by: ['date'], date_grain: 'day', limit: 100, ...scope },
        controller.signal,
      ),
      queryMetric(
        { metric: 'revenue', group_by: ['product'], limit: 100, ...scope },
        controller.signal,
      ),
      queryMetric({ metric: 'revenue', group_by: ['store_category'], ...scope }, controller.signal),
      getQualitySummary(controller.signal),
      getInsights(controller.signal),
    ])
      .then(([revenue, orders, aov, trend, products, categories, quality, insights]) => {
        setData({ revenue, orders, aov, trend, products, categories, quality, insights })
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return
        setError(requestError instanceof Error ? requestError.message : '数据加载失败')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [appliedRange])

  const trendData = useMemo(
    () =>
      data?.trend.points.map((point) => ({
        date: point.dimensions.date.slice(5),
        revenue: point.value / 100,
      })) ?? [],
    [data],
  )
  const productData = useMemo(
    () =>
      (data?.products.points ?? [])
        .map((point) => ({ name: point.dimensions.product, revenue: point.value / 100 }))
        .sort((a, b) => b.revenue - a.revenue)
        .slice(0, 10),
    [data],
  )
  const categoryData = useMemo(
    () =>
      (data?.categories.points ?? [])
        .map((point) => ({ name: point.dimensions.store_category, value: point.value }))
        .sort((a, b) => b.value - a.value),
    [data],
  )

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" aria-label="Proofline 首页">
          <span className="brand-mark">P</span>
          <span>Proofline</span>
        </a>
        <nav className="nav" aria-label="主导航">
          <a className="nav-item active" href="#overview">
            <span>◫</span>经营总览
          </a>
          <a className="nav-item" href="#products">
            <span>◇</span>商品分析
          </a>
          <a className="nav-item" href="#quality">
            <span>✓</span>数据质量
          </a>
          <button className="nav-item" onClick={() => setAssistantOpen(true)}>
            <span>✦</span>分析助手
          </button>
        </nav>
        <div className="workspace-card">
          <span className="workspace-avatar">M</span>
          <div>
            <strong>Moneki</strong>
            <small>餐饮经营空间</small>
          </div>
          <span className="workspace-chevron">⌄</span>
        </div>
      </aside>

      <main className="main" id="top">
        <header className="topbar">
          <div>
            <p className="eyebrow">经营分析 / 总览</p>
            <h1>经营总览</h1>
          </div>
          <div className="topbar-actions">
            <span className="verified-pill">
              <i /> 已连接可信数据
            </span>
            <button className="icon-button" aria-label="通知">
              ●
            </button>
            <span className="user-avatar">贺</span>
          </div>
        </header>

        <section className="filter-bar" aria-label="日期筛选">
          <div className="filter-copy">
            <span className="filter-icon">⌁</span>
            <div>
              <strong>分析范围</strong>
              <small>所有指标共享同一筛选口径</small>
            </div>
          </div>
          <label>
            开始日期
            <input
              ref={dateFromRef}
              type="date"
              value={dateFrom}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <span className="range-dash">—</span>
          <label>
            结束日期
            <input
              ref={dateToRef}
              type="date"
              value={dateTo}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            onClick={() => {
              const from = dateFromRef.current?.value ?? dateFrom
              const to = dateToRef.current?.value ?? dateTo
              if (from <= to) setAppliedRange({ from, to })
            }}
          >
            应用筛选
          </button>
        </section>

        {error && (
          <div className="error-state">
            <strong>暂时无法读取分析数据</strong>
            <span>{error}</span>
            <small>请确认后端已启动并完成 ingest 与 process。</small>
          </div>
        )}

        <section className="kpi-grid" id="overview" aria-busy={loading}>
          <KpiCard
            label="净营业额"
            value={data ? formatCurrency(data.revenue.points[0]?.value ?? 0) : '—'}
            hint="含有效退款扣减"
            evidence={data?.revenue.evidence.evidence_id}
            accent
          />
          <KpiCard
            label="有效订单"
            value={data ? integer.format(data.orders.points[0]?.value ?? 0) : '—'}
            hint="唯一订单号"
            evidence={data?.orders.evidence.evidence_id}
          />
          <KpiCard
            label="平均客单价"
            value={data ? formatCurrency(data.aov.points[0]?.value ?? 0) : '—'}
            hint="净营业额 ÷ 订单数"
            evidence={data?.aov.evidence.evidence_id}
          />
          <KpiCard
            label="可信记录率"
            value={data ? `${data.quality.acceptance_rate}%` : '—'}
            hint={
              data
                ? `${integer.format(data.quality.accepted_sales_records)} 条进入分析层`
                : '清洗完成后展示'
            }
            evidence={data ? `run-${data.quality.processing_run_id}` : undefined}
          />
        </section>

        <section className="content-grid">
          <article className="panel trend-panel">
            <PanelHeader
              title="每日营业额趋势"
              subtitle="已接受销售记录 · 单位：人民币"
              badge={data?.trend.evidence.evidence_id}
            />
            <div className="chart-area">
              <Suspense fallback={<div className="chart-loading">正在加载趋势…</div>}>
                <TrendChart data={trendData} />
              </Suspense>
            </div>
          </article>

          <article className="panel quality-panel" id="quality">
            <PanelHeader title="数据质量" subtitle="本次处理批次的可审计结果" />
            <div className="quality-score">
              <strong>
                {data?.quality.acceptance_rate ?? '—'}
                <small>%</small>
              </strong>
              <span>可信记录率</span>
            </div>
            <div className="quality-track">
              <span style={{ width: `${data?.quality.acceptance_rate ?? 0}%` }} />
            </div>
            <dl className="quality-list">
              <div>
                <dt>自动修复</dt>
                <dd>{integer.format(data?.quality.repair_events ?? 0)}</dd>
              </div>
              <div>
                <dt>规范化去重</dt>
                <dd>{integer.format(data?.quality.deduplicated_records ?? 0)}</dd>
              </div>
              <div>
                <dt>隔离待核验</dt>
                <dd>{integer.format(data?.quality.quarantined_records ?? 0)}</dd>
              </div>
              <div>
                <dt>保留退款</dt>
                <dd>{integer.format(data?.quality.refund_records ?? 0)}</dd>
              </div>
            </dl>
            <a
              className="text-link"
              href="https://github.com/718232157/proofline-analytics/blob/main/docs/DATA_QUALITY.md"
            >
              查看清洗口径 <span>→</span>
            </a>
          </article>

          <article className="panel products-panel" id="products">
            <PanelHeader
              title="营业额前 10 商品"
              subtitle="按净营业额排序"
              badge={data?.products.evidence.evidence_id}
            />
            <div className="bar-chart-area">
              <Suspense fallback={<div className="chart-loading">正在加载商品排行…</div>}>
                <ProductsChart data={productData} />
              </Suspense>
            </div>
          </article>

          <article className="panel category-panel">
            <PanelHeader
              title="门店品类贡献"
              subtitle="净营业额结构"
              badge={data?.categories.evidence.evidence_id}
            />
            <div className="category-list">
              {categoryData.map((item, index) => (
                <div className="category-row" key={item.name}>
                  <span className="category-rank">0{index + 1}</span>
                  <div>
                    <strong>{item.name}</strong>
                    <small>{formatCurrency(item.value)}</small>
                  </div>
                  <div className="category-meter">
                    <span
                      style={{ width: `${(item.value / (categoryData[0]?.value || 1)) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section className="insight-feed" aria-label="主动经营洞察">
          <header>
            <div>
              <p className="eyebrow">主动经营信号</p>
              <h2>经营脉搏</h2>
            </div>
            <span>基于 {data?.insights?.period ?? '最新完整月份'}</span>
          </header>
          <div className="insight-cards">
            {(data?.insights?.insights ?? []).map((insight) => (
              <article className={`insight-card ${insight.tone}`} key={insight.kind}>
                <span className="insight-symbol">
                  {insight.kind === 'performance_pulse' ? '↗' : '◎'}
                </span>
                <div>
                  <strong>{insight.title}</strong>
                  <p>{insight.narrative}</p>
                  <code>{insight.evidence_ids.map((id) => `#${id.slice(0, 6)}`).join(' · ')}</code>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="assistant-strip" id="assistant">
          <span className="assistant-spark">✦</span>
          <div>
            <strong>从证据继续追问</strong>
            <p>分析助手只会引用上面的治理指标，不会绕过口径自由生成数字。</p>
          </div>
          <div className="question-chips">
            <button onClick={() => setAssistantOpen(true)}>哪个品类营业额最高？</button>
            <button onClick={() => setAssistantOpen(true)}>牛肉 poke 六月卖了多少？</button>
          </div>
        </section>
      </main>
      <AssistantDrawer
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        onApplyQuery={(query: AnalyticsQuery) => {
          if (query.date_from && query.date_to) {
            setDateFrom(query.date_from)
            setDateTo(query.date_to)
            setAppliedRange({ from: query.date_from, to: query.date_to })
          }
          document.getElementById('overview')?.scrollIntoView({ behavior: 'smooth' })
        }}
      />
    </div>
  )
}

function KpiCard({
  label,
  value,
  hint,
  evidence,
  accent = false,
}: {
  label: string
  value: string
  hint: string
  evidence?: string
  accent?: boolean
}) {
  return (
    <article className={`kpi-card${accent ? ' accent' : ''}`}>
      <div className="kpi-label">
        <span>{label}</span>
        <i title="指标口径已治理">i</i>
      </div>
      <strong>{value}</strong>
      <div className="kpi-footer">
        <span>{hint}</span>
        {evidence && <code>#{evidence.slice(0, 8)}</code>}
      </div>
    </article>
  )
}

function PanelHeader({
  title,
  subtitle,
  badge,
}: {
  title: string
  subtitle: string
  badge?: string
}) {
  return (
    <header className="panel-header">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {badge && <span className="evidence-badge">证据 #{badge.slice(0, 8)}</span>}
    </header>
  )
}

export default App
