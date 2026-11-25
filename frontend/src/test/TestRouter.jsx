import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { SyncContext } from '../contexts/SyncContext';
import { AuthContext, AuthProvider } from '../contexts/AuthContext';

const ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
};

const defaultSyncValue = {
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: null,
    cohorts: {},
    revenue: { months: [] },
    courses: [],
    financials: null,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  updateSyncStatus: vi.fn(),
  selectedCourseIds: null,
  isFilterActive: false,
  toggleCourse: vi.fn(),
  selectAllCourses: vi.fn(),
  selectNoneCourses: vi.fn(),
};

export default function TestRouter({ children, initialEntries = ['/'], syncValue, authValue }) {
  const value = syncValue || defaultSyncValue;
  const content = <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
  return (
    <MemoryRouter future={ROUTER_FUTURE} initialEntries={initialEntries}>
      {authValue ? (
        <AuthContext.Provider value={authValue}>{content}</AuthContext.Provider>
      ) : (
        <AuthProvider>{content}</AuthProvider>
      )}
    </MemoryRouter>
  );
}
