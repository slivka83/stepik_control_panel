import { MemoryRouter } from 'react-router-dom'

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
}

export default function TestRouter({ children, initialEntries = ['/'] }) {
  return (
    <MemoryRouter future={ROUTER_FUTURE} initialEntries={initialEntries}>
      {children}
    </MemoryRouter>
  )
}
