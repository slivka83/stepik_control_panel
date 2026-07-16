import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { SyncProvider } from './contexts/SyncContext.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <SyncProvider>
        <App />
      </SyncProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
