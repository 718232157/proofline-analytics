import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { AssistantDrawer } from './AssistantDrawer'
import { EvidenceStatus } from './EvidenceStatus'
import {
  getQualitySummary,
  getInsights,
  queryMetric,
  type ChartAction,
  type ChartTarget,
  type MetricResult,
  type QualitySummary,
  type InsightFeed,
} from './api'

const TrendChart = lazy(() => import('./charts').then((module) => ({ default: module.TrendChart })))
const ProductsChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.ProductsChart })),
)
const AovTrendChart = lazy(() =>
  import('./charts').then((module) => ({ default: module.AovTrendChart })),
)

type DashboardData = {
  revenue: MetricResult
  orders: MetricResult
  aov: MetricResult
  trend: MetricResult
  products: MetricResult
  categories: MetricResult
  monthlyAov: MetricResult
  storeRevenue: MetricResult
  storeOrders: MetricResult
  storeAov: MetricResult
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
const DEFAULT_DATE_FROM = '2026-05-01'
const DEFAULT_DATE_TO = '2026-07-31'
const filterLabels: Record<string, string> = {
  product: '商品',
  product_category: '商品品类',
  store: '门店',
  store_category: '门店品类',
}

function App() {
  const [dateFrom, setDateFrom] = useState(DEFAULT_DATE_FROM)
  const [dateTo, setDateTo] = useState(DEFAULT_DATE_TO)
  const [dateError, setDateError] = useState<string | null>(null)
  const dateFromRef = useRef<HTMLInputElement>(null)
  const dateToRef = useRef<HTMLInputElement>(null)
  const [appliedRange, setAppliedRange] = useState({ from: dateFrom, to: dateTo })
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [activeFilters, setActiveFilters] = useState<Record<string, string[]>>({})
  const [focused, setFocused] = useState<{ target: ChartTarget; highlight: string | null } | null>(
    null,
  )

  useEffect(() => {
    const controller = new AbortController()
    const scope = {
      date_from: appliedRange.from,
      date_to: appliedRange.to,
      ...(Object.keys(activeFilters).length > 0 ? { filters: activeFilters } : {}),
    }
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
      queryMetric(
        { metric: 'average_order_value', group_by: ['date'], date_grain: 'month', ...scope },
        controller.signal,
      ),
      queryMetric({ metric: 'revenue', group_by: ['store'], ...scope }, controller.signal),
      queryMetric({ metric: 'order_count', group_by: ['store'], ...scope }, controller.signal),
      queryMetric(
        { metric: 'average_order_value', group_by: ['store'], ...scope },
        controller.signal,
      ),
      getQualitySummary(controller.signal),
      getInsights(controller.signal),
    ])
      .then(
        ([
          revenue,
          orders,
          aov,
          trend,
          products,
          categories,
          monthlyAov,
          storeRevenue,
          storeOrders,
          storeAov,
          quality,
          insights,
        ]) => {
          setData({
            revenue,
            orders,
            aov,
            trend,
            products,
            categories,
            monthlyAov,
            storeRevenue,
            storeOrders,
            storeAov,
            quality,
            insights,
          })
        },
      )
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return
        setError(requestError instanceof Error ? requestError.message : '数据加载失败')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [appliedRange, activeFilters])

  const trendData = useMemo(
    () =>
      data?.trend.points.map((point) => ({
        date: point.dimensions.date,
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
  const monthlyAovData = useMemo(
    () =>
      (data?.monthlyAov.points ?? []).map((point) => ({
        month: point.dimensions.date,
        value: point.value / 100,
      })),
    [data],
  )
  const storeData = useMemo(() => {
    const revenue = new Map(
      (data?.storeRevenue.points ?? []).map((point) => [point.dimensions.store, point.value]),
    )
    const orders = new Map(
      (data?.storeOrders.points ?? []).map((point) => [point.dimensions.store, point.value]),
    )
    const aov = new Map(
      (data?.storeAov.points ?? []).map((point) => [point.dimensions.store, point.value]),
    )
    return [...revenue.entries()]
      .map(([name, value]) => ({
        name,
        revenue: value,
        orders: orders.get(name) ?? 0,
        aov: aov.get(name) ?? 0,
      }))
      .sort((left, right) => right.revenue - left.revenue)
  }, [data])
  const activeFilterEntries = Object.entries(activeFilters).flatMap(([dimension, values]) =>
    values.map((value) => ({ dimension, value })),
  )

  const connectionState = error ? 'error' : loading ? 'loading' : 'connected'
  const connectionLabel = error ? '数据连接异常' : loading ? '正在校验数据' : '已连接可信数据'

  const focusSection = (target: ChartTarget, highlight: string | null = null) => {
    setFocused({ target, highlight })
    window.setTimeout(() => {
      document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 80)
    window.setTimeout(() => setFocused(null), 2400)
  }

  const applyChartAction = (action: ChartAction) => {
    const { query } = action
    const from = query.date_from ?? DEFAULT_DATE_FROM
    const to = query.date_to ?? DEFAULT_DATE_TO
    setDateFrom(from)
    setDateTo(to)
    setAppliedRange({ from, to })
    setActiveFilters(query.filters ? { ...query.filters } : {})
    focusSection(action.target, action.highlight)
  }

  return (
    <div className={`app-shell${assistantOpen ? ' assistant-open' : ''}`}>
      <main className="main" id="top">
        <header className="topbar">
          <div className="topbar-identity">
            <a className="brand" href="#top" aria-label="Proofline 首页">
              <span className="brand-mark">P</span>
              <span>Proofline</span>
            </a>
            <span className="topbar-divider" aria-hidden="true" />
            <div className="page-heading">
              <p className="eyebrow">Moneki · 餐饮经营空间</p>
              <h1>经营总览</h1>
            </div>
          </div>
          <div className="topbar-actions">
            <span
              className={`verified-pill ${connectionState}`}
              role="status"
              title="状态来自当前 API 请求，不是静态装饰"
            >
              <i /> {connectionLabel}
            </span>
            <button
              className={`assistant-entry${assistantOpen ? ' active' : ''}`}
              onClick={() => setAssistantOpen((current) => !current)}
              aria-expanded={assistantOpen}
              aria-controls="analysis-assistant"
              aria-label={assistantOpen ? '收起分析助手' : '打开分析助手'}
            >
              <span aria-hidden="true">✦</span>
              <span className="assistant-entry-label">分析助手</span>
            </button>
          </div>
        </header>

        <section className="filter-bar" aria-label="日期筛选">
          <div className="filter-copy">
            <span className="filter-icon">⌁</span>
            <div>
              <strong>分析范围</strong>
              <small>所有指标共享同一筛选口径 · 展示币种 CNY</small>
            </div>
          </div>
          <label>
            开始日期
            <input
              ref={dateFromRef}
              type="date"
              value={dateFrom}
              max={dateTo}
              aria-invalid={Boolean(dateError)}
              onChange={(event) => {
                setDateFrom(event.target.value)
                setDateError(null)
              }}
            />
          </label>
          <span className="range-dash">—</span>
          <label>
            结束日期
            <input
              ref={dateToRef}
              type="date"
              value={dateTo}
              min={dateFrom}
              aria-invalid={Boolean(dateError)}
              onChange={(event) => {
                setDateTo(event.target.value)
                setDateError(null)
              }}
            />
          </label>
          <button
            className="primary-button"
            onClick={() => {
              const from = dateFromRef.current?.value ?? dateFrom
              const to = dateToRef.current?.value ?? dateTo
              if (from > to) {
                setDateError('开始日期不能晚于结束日期')
                return
              }
              setDateError(null)
              setAppliedRange({ from, to })
            }}
          >
            应用筛选
          </button>
          {dateError && <span className="filter-error">{dateError}</span>}
        </section>

        {activeFilterEntries.length > 0 && (
          <section className="scope-banner" aria-label="当前经营筛选">
            <div>
              <strong>当前经营范围</strong>
              {activeFilterEntries.map(({ dimension, value }) => (
                <span key={`${dimension}-${value}`}>
                  {filterLabels[dimension] ?? dimension} · {value}
                </span>
              ))}
            </div>
            <button onClick={() => setActiveFilters({})}>清除 AI 筛选</button>
          </section>
        )}

        {error && (
          <div className="error-state">
            <strong>暂时无法读取分析数据</strong>
            <span>{error}</span>
            <small>请确认后端已启动并完成 ingest 与 process。</small>
          </div>
        )}

        <section className="decision-radar" aria-label="可信经营雷达">
          <header>
            <div>
              <p className="eyebrow">最新营业日 · 主动发现</p>
              <h2>可信经营雷达</h2>
              <span>按影响与紧迫度排序，每条建议都来自治理指标。</span>
            </div>
            {data ? (
              <EvidenceStatus
                evidenceIds={data.insights.insights.flatMap((insight) => insight.evidence_ids)}
                label="全部结论已核验"
              />
            ) : (
              <span className="radar-loading">正在核验最新经营信号…</span>
            )}
          </header>
          <div className="radar-list">
            {(data?.insights.insights ?? []).map((insight, index) => (
              <article className={`radar-item ${insight.tone}`} key={insight.kind}>
                <span className="radar-order">0{index + 1}</span>
                <div className="radar-copy">
                  <div className="radar-title-row">
                    <strong>{insight.title}</strong>
                    <span className={`priority ${insight.priority}`}>
                      {insight.priority === 'high'
                        ? insight.tone === 'watch'
                          ? '优先处理'
                          : '增长机会'
                        : insight.priority === 'medium'
                          ? '建议关注'
                          : '经营正常'}
                    </span>
                  </div>
                  <p>{insight.narrative}</p>
                  <small>行动建议：{insight.action}</small>
                </div>
                <div className="radar-action">
                  <b>{insight.impact_display}</b>
                  <button onClick={() => focusSection(insight.target, insight.highlight)}>
                    查看依据 →
                  </button>
                </div>
              </article>
            ))}
            {!loading && (data?.insights.insights.length ?? 0) === 0 && (
              <p className="empty-table">当前没有可生成的经营信号。</p>
            )}
          </div>
        </section>

        <section
          className={`kpi-grid${focused?.target === 'overview' ? ' focus-pulse' : ''}`}
          id="overview"
          aria-busy={loading}
        >
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
          <article
            className={`panel trend-panel${focused?.target === 'revenue_trend' ? ' focus-pulse' : ''}`}
            id="revenue_trend"
          >
            <PanelHeader
              title="每日营业额趋势"
              subtitle="已接受销售记录 · 展示币种：CNY（工作区配置）"
              badge={data?.trend.evidence.evidence_id}
            />
            <div className="chart-area">
              {data && trendData.length === 0 ? (
                <div className="chart-empty">当前筛选范围内没有已接受的销售记录</div>
              ) : (
                <Suspense fallback={<div className="chart-loading">正在加载趋势…</div>}>
                  <TrendChart data={trendData} />
                </Suspense>
              )}
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

          <article
            className={`panel products-panel${focused?.target === 'product_ranking' ? ' focus-pulse' : ''}`}
            id="product_ranking"
          >
            <PanelHeader
              title={activeFilters.product ? '已选商品营业额' : '营业额前 10 商品'}
              subtitle="图表看结构，表格核对精确值"
              badge={data?.products.evidence.evidence_id}
            />
            <div className="product-ranking">
              <div className="bar-chart-area">
                <Suspense fallback={<div className="chart-loading">正在加载商品排行…</div>}>
                  <ProductsChart data={productData} />
                </Suspense>
              </div>
              <div className="product-table-wrap">
                <table className="product-table">
                  <caption className="sr-only">商品净营业额排名</caption>
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>商品</th>
                      <th>净营业额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productData.map((item, index) => (
                      <tr
                        className={focused?.highlight === item.name ? 'row-highlight' : ''}
                        key={item.name}
                      >
                        <td>{index + 1}</td>
                        <td>{item.name}</td>
                        <td>{currency.format(item.revenue)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!loading && productData.length === 0 && (
                  <p className="empty-table">当前筛选下没有可信销售记录。</p>
                )}
              </div>
            </div>
          </article>

          <article
            className={`panel category-panel${focused?.target === 'category_contribution' ? ' focus-pulse' : ''}`}
            id="category_contribution"
          >
            <PanelHeader
              title="门店品类贡献"
              subtitle="净营业额结构"
              badge={data?.categories.evidence.evidence_id}
            />
            <div className="category-list">
              {categoryData.map((item, index) => (
                <div
                  className={`category-row${focused?.highlight === item.name ? ' row-highlight' : ''}`}
                  key={item.name}
                >
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

        <section className="decision-grid">
          <article
            className={`panel aov-panel${focused?.target === 'aov_trend' ? ' focus-pulse' : ''}`}
            id="aov_trend"
          >
            <PanelHeader
              title="月度客单价趋势"
              subtitle="净营业额 ÷ 唯一有效订单数"
              badge={data?.monthlyAov.evidence.evidence_id}
            />
            <div className="aov-chart-area">
              {data && monthlyAovData.length === 0 ? (
                <div className="chart-empty">当前筛选范围内没有可计算客单价的有效订单</div>
              ) : (
                <Suspense fallback={<div className="chart-loading">正在加载客单价趋势…</div>}>
                  <AovTrendChart data={monthlyAovData} />
                </Suspense>
              )}
            </div>
          </article>

          <article
            className={`panel store-panel${focused?.target === 'store_comparison' ? ' focus-pulse' : ''}`}
            id="store_comparison"
          >
            <PanelHeader
              title="门店经营对比"
              subtitle="同一口径比较营业额、订单数与客单价"
              badge={data?.storeRevenue.evidence.evidence_id}
            />
            <div className="store-table-wrap">
              <table className="store-table">
                <thead>
                  <tr>
                    <th>门店</th>
                    <th>净营业额</th>
                    <th>订单数</th>
                    <th>客单价</th>
                    <th>相对最高门店</th>
                  </tr>
                </thead>
                <tbody>
                  {storeData.map((store) => (
                    <tr
                      className={focused?.highlight === store.name ? 'row-highlight' : ''}
                      key={store.name}
                    >
                      <td>{store.name}</td>
                      <td>{formatCurrency(store.revenue)}</td>
                      <td>{integer.format(store.orders)}</td>
                      <td>{formatCurrency(store.aov)}</td>
                      <td>
                        <span className="store-meter">
                          <i
                            style={{
                              width: `${(store.revenue / (storeData[0]?.revenue || 1)) * 100}%`,
                            }}
                          />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!loading && storeData.length === 0 && (
                <p className="empty-table">当前筛选下没有可比较的门店数据。</p>
              )}
            </div>
          </article>
        </section>

        <section className="product-note" aria-label="币种说明">
          <strong>口径说明</strong>
          <span>
            原始文件未声明币种；当前工作区根据中文餐饮场景和部分 ¥ 记录配置为
            CNY，配置只影响展示，不改变原始金额计算。
          </span>
        </section>
      </main>
      <AssistantDrawer
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        onApplyQuery={applyChartAction}
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
        {evidence && <EvidenceStatus evidenceIds={evidence} />}
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
      {badge && <EvidenceStatus evidenceIds={badge} />}
    </header>
  )
}

export default App
