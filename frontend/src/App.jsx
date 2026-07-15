import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Courses from './pages/Courses'
import Financials from './pages/Financials'
import Cohorts from './pages/Cohorts'

function App() {
  return (
    <AuthProvider>
      <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/courses" element={<Courses />} />
            <Route path="/financials" element={<Financials />} />
            <Route path="/cohorts" element={<Cohorts />} />
          </Routes>
        </Layout>
      </Router>
    </AuthProvider>
  )
}

export default App
