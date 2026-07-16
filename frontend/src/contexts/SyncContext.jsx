import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api'

const SyncContext = createContext()

export function SyncProvider({ children }) {
  const [syncStatus, setSyncStatus] = useState({ in_progress: false, last_sync: null })
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let lastKnownSync = null

    const poll = async () => {
      try {
        const { data } = await api.get('/api/sync/status')
        setSyncStatus(data)
        if (lastKnownSync && data.last_sync && lastKnownSync !== data.last_sync) {
          setRefreshKey(k => k + 1)
        }
        lastKnownSync = data.last_sync
      } catch {}
    }

    poll()
    const interval = setInterval(poll, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <SyncContext.Provider value={{ syncStatus, refreshKey }}>
      {children}
    </SyncContext.Provider>
  )
}

export const useSync = () => useContext(SyncContext)
