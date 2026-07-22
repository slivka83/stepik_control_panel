import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null, errorInfo: null }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo })
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen bg-space-black text-white p-8">
          <div className="glass-panel p-6 max-w-2xl mx-auto mt-20">
            <h1 className="text-crimson-alert text-xl font-bold mb-4">
              Ошибка приложения
            </h1>
            <div className="bg-space-black rounded-lg p-4 mb-4 overflow-auto">
              <pre className="text-crimson-alert text-sm font-mono whitespace-pre-wrap">
                {this.state.error?.message}
              </pre>
            </div>
            {this.state.errorInfo && (
              <details className="mb-4">
                <summary className="text-gray-400 text-sm cursor-pointer hover:text-gray-300">
                  Трассировка стека
                </summary>
                <pre className="text-gray-500 text-xs font-mono mt-2 whitespace-pre-wrap overflow-auto max-h-64">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors"
            >
              Перезагрузить
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
