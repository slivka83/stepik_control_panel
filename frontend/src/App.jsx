import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Courses from './pages/Courses'
import Financials from './pages/Financials'
import Cohorts from './pages/Cohorts'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/financials" element={<Financials />} />
          <Route path="/cohorts" element={<Cohorts />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
