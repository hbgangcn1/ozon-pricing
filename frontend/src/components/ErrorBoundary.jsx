import { Component } from 'react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', gap: 16 }}>
          <p style={{ fontSize: 16, color: '#a1a1aa' }}>页面发生了意外错误，请尝试重新加载。</p>
          <button
            onClick={() => window.location.reload()}
            style={{ padding: '8px 20px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 14 }}
          >
            重新加载
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
