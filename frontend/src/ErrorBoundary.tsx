import { Component, type ErrorInfo, type ReactNode } from 'react'

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Proofline 页面渲染失败', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="fatal-state">
          <span className="brand-mark">P</span>
          <p className="eyebrow">安全降级</p>
          <h1>页面没有正确加载</h1>
          <p>你的数据没有被修改。请刷新页面；如果问题持续存在，请检查浏览器控制台。</p>
          <button onClick={() => window.location.reload()}>重新加载</button>
        </main>
      )
    }
    return this.props.children
  }
}
