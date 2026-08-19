import { useEffect, useRef, useState, type FormEvent } from 'react'
import { streamAssistant, type AnalysisContext, type ChartAction, type ChatResponse } from './api'
import { EvidenceStatus } from './EvidenceStatus'

type Message =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; response: ChatResponse }

const suggestions = [
  '哪个品类的门店营业额最高？',
  '牛肉 poke 六月卖了多少钱？',
  '客单价最近是涨了还是跌了？',
  '五家门店经营表现有什么差异？',
]

export function AssistantDrawer({
  open,
  onClose,
  onApplyQuery,
}: {
  open: boolean
  onClose: () => void
  onApplyQuery: (action: ChartAction) => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [context, setContext] = useState<AnalysisContext | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState('')
  const nextId = useRef(1)

  useEffect(() => {
    if (!open) return

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }

    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [open, onClose])

  const submit = async (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || loading) return
    const userMessage: Message = { id: nextId.current++, role: 'user', text: trimmed }
    setMessages((current) => [...current, userMessage])
    setInput('')
    setLoading(true)
    try {
      const response = await streamAssistant(trimmed, context, setProgress)
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', response }])
      setContext(response.context)
    } catch (error) {
      const message = error instanceof Error ? error.message : '请求失败'
      setMessages((current) => [
        ...current,
        {
          id: nextId.current++,
          role: 'assistant',
          response: {
            status: 'unsupported',
            answer: `分析服务暂时不可用：${message}`,
            context: null,
            citations: [],
            chart_action: null,
          },
        },
      ])
    } finally {
      setLoading(false)
      setProgress('')
    }
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit(input)
  }

  return (
    <>
      <button
        className={`drawer-backdrop${open ? ' open' : ''}`}
        aria-label="关闭分析助手"
        onClick={onClose}
      />
      <aside
        id="analysis-assistant"
        className={`assistant-drawer${open ? ' open' : ''}`}
        aria-label="证据分析助手"
        aria-hidden={!open}
      >
        <header className="drawer-header">
          <div className="drawer-title">
            <span>✦</span>
            <div>
              <strong>证据分析助手</strong>
              <small>每个数字都来自治理指标</small>
            </div>
          </div>
          <button onClick={onClose} aria-label="关闭">
            ×
          </button>
        </header>

        <div className="conversation" aria-live="polite">
          {messages.length === 0 && (
            <div className="assistant-welcome">
              <span>✦</span>
              <h2>今天想看什么？</h2>
              <p>我会调用可信数据工具，并把口径、范围和证据一起交给你。</p>
              <div className="assistant-suggestions">
                {suggestions.map((question) => (
                  <button key={question} onClick={() => void submit(question)}>
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((message) =>
            message.role === 'user' ? (
              <div className="chat-message user" key={message.id}>
                {message.text}
              </div>
            ) : (
              <div className="chat-answer" key={message.id}>
                <div className="assistant-icon">✦</div>
                <div>
                  <p>{message.response.answer}</p>
                  {message.response.citations.map((citation) => (
                    <div
                      className="citation-card"
                      key={`${message.id}-${citation.evidence_id}-${citation.display_value}`}
                    >
                      <div>
                        <span>{citation.label}</span>
                        <strong>{citation.display_value}</strong>
                      </div>
                      <small>{formatScope(citation.scope)}</small>
                      <EvidenceStatus
                        evidenceIds={citation.evidence_id}
                        label={`真实查询已核验 · 数据批次 ${citation.processing_run_id}`}
                      />
                    </div>
                  ))}
                  {message.response.chart_action && (
                    <button
                      className="apply-answer"
                      onClick={() => {
                        onApplyQuery(message.response.chart_action!)
                        onClose()
                      }}
                    >
                      按此口径查看看板 →
                    </button>
                  )}
                </div>
              </div>
            ),
          )}
          {loading && (
            <div className="thinking">
              <i />
              <i />
              <i />
              <span>{progress || '正在查询治理指标'}</span>
            </div>
          )}
        </div>

        <form className="assistant-input" onSubmit={handleSubmit}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="追问：那五月呢？"
            aria-label="向分析助手提问"
          />
          <button type="submit" disabled={loading || !input.trim()} aria-label="发送问题">
            ↑
          </button>
          <small>AI 只解释工具结果，可能拒绝超出数据范围的问题。</small>
        </form>
      </aside>
    </>
  )
}

function formatScope(scope: string) {
  if (scope === 'all accepted records') return '全部可信记录'
  const labels: Record<string, string> = {
    date: '日期',
    product: '商品',
    product_category: '商品品类',
    store: '门店',
    store_category: '门店品类',
  }
  return scope
    .split('; ')
    .map((part) => {
      const [key, value] = part.split('=', 2)
      if (!value) return part
      if (key === 'group_by') return `按${labels[value] ?? value}汇总`
      return `${labels[key] ?? key}：${value}`
    })
    .join(' · ')
}
