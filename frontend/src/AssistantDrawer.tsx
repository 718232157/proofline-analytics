import { useRef, useState, type FormEvent } from 'react'
import { askAssistant, type AnalysisContext, type AnalyticsQuery, type ChatResponse } from './api'

type Message =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; response: ChatResponse }

const suggestions = [
  '哪个品类的门店营业额最高？',
  '牛肉 poke 六月卖了多少钱？',
  '客单价最近是涨了还是跌了？',
]

export function AssistantDrawer({
  open,
  onClose,
  onApplyQuery,
}: {
  open: boolean
  onClose: () => void
  onApplyQuery: (query: AnalyticsQuery) => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [context, setContext] = useState<AnalysisContext | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const nextId = useRef(1)

  const submit = async (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || loading) return
    const userMessage: Message = { id: nextId.current++, role: 'user', text: trimmed }
    setMessages((current) => [...current, userMessage])
    setInput('')
    setLoading(true)
    try {
      const response = await askAssistant(trimmed, context)
      setMessages((current) => [...current, { id: nextId.current++, role: 'assistant', response }])
      setContext(response.context)
      if (response.chart_action) onApplyQuery(response.chart_action.query)
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
      <aside className={`assistant-drawer${open ? ' open' : ''}`} aria-hidden={!open}>
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
                      <small>{citation.scope}</small>
                      <code>
                        证据 #{citation.evidence_id.slice(0, 8)} · run {citation.processing_run_id}
                      </code>
                    </div>
                  ))}
                  {message.response.chart_action && (
                    <button
                      className="apply-answer"
                      onClick={() => onApplyQuery(message.response.chart_action!.query)}
                    >
                      同步到看板 →
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
              <span>正在查询治理指标</span>
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
