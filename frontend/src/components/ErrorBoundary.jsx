import { Component } from 'react'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen gap-4">
          <p className="text-base text-text-muted">页面发生了意外错误，请尝试重新加载。</p>
          <button
            onClick={() => window.location.reload()}
            className="px-5 py-2 bg-primary text-white border-none rounded-md cursor-pointer text-sm hover:bg-primary-dim transition-colors duration-200"
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
