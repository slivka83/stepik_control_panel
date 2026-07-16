import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../contexts/AuthContext'
import { SyncProvider } from '../contexts/SyncContext'

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
}

export default function TestRouter({ children, initialEntries = ['/'] }) {
  return (
    <MemoryRouter future={ROUTER_FUTURE} initialEntries={initialEntries}>
      <AuthProvider>
        <SyncProvider>
          {children}
        </SyncProvider>
      </AuthProvider>
    </MemoryRouter>
  )
}
