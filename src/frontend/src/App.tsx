import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import SignalsPage from './pages/Signals'
import SignalDetailPage from './pages/SignalDetail'
import SubmissionPage from './pages/Submission'
import GapReportPage from './pages/GapReport'
import BobAIPage from './pages/BobAI'
import styles from './App.module.css'

function NotFound() {
  return (
    <div className={styles.notFound}>
      <h1>404</h1>
      <p>Page not found.</p>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/"                        element={<Dashboard />} />
          <Route path="/signals"                 element={<SignalsPage />} />
          <Route path="/signals/:drug/:event"    element={<SignalDetailPage />} />
          <Route path="/submission"              element={<SubmissionPage />} />
          <Route path="/gaps"                    element={<GapReportPage />} />
          <Route path="/gaps/:id"                element={<GapReportPage />} />
          <Route path="/bob"                     element={<BobAIPage />} />
          <Route path="*"                        element={<NotFound />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
