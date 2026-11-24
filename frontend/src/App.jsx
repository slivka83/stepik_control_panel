import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Courses = lazy(() => import('./pages/Courses'));
const Solutions = lazy(() => import('./pages/Solutions'));
const Comments = lazy(() => import('./pages/Comments'));
const Financials = lazy(() => import('./pages/Financials'));
const Students = lazy(() => import('./pages/Students'));
const Activities = lazy(() => import('./pages/Activities'));
const Certificates = lazy(() => import('./pages/Certificates'));
const Reviews = lazy(() => import('./pages/Reviews'));
const NotFound = lazy(() => import('./pages/NotFound'));

// Code splitting without a loading placeholder: the UI contract forbids
// skeletons/"Загрузка..." that replace real cards (they cause layout flicker).
// Pages render their real empty-state components as soon as the chunk loads.
function App() {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Layout>
        <Suspense fallback={null}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/solutions" element={<Solutions />} />
            <Route path="/comments" element={<Comments />} />
            <Route path="/financials" element={<Financials />} />
            <Route path="/students" element={<Students />} />
            <Route path="/activities" element={<Activities />} />
            <Route path="/certificates" element={<Certificates />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </Layout>
    </Router>
  );
}

export default App;
