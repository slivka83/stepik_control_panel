import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Courses = lazy(() => import('./pages/Courses'));
const Solutions = lazy(() => import('./pages/Solutions'));
const Financials = lazy(() => import('./pages/Financials'));
const Students = lazy(() => import('./pages/Students'));
const Activities = lazy(() => import('./pages/Activities'));
const NotFound = lazy(() => import('./pages/NotFound'));

function PageSkeleton() {
  return (
    <div className="animate-pulse space-y-6 p-6">
      <div className="h-8 bg-space-gray rounded w-1/3" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-space-gray rounded-xl" />
        ))}
      </div>
      <div className="h-64 bg-space-gray rounded-xl" />
    </div>
  );
}

function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Layout>
        <Suspense fallback={<PageSkeleton />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/solutions" element={<Solutions />} />
            <Route path="/financials" element={<Financials />} />
            <Route path="/students" element={<Students />} />
            <Route path="/activities" element={<Activities />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </Router>
  );
}

export default App;
