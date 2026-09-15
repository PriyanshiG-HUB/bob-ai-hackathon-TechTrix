import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Database,
  Pill,
  Heartbeat,
  LinkSimple,
  ShieldWarning,
} from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import StatCard from '../components/StatCard'
import SignalTable from '../components/SignalTable'
import Disclaimer from '../components/Disclaimer'
import ErrorState from '../components/ErrorState'
import { fetchStats, fetchSignals, extractErrorMessage } from '../services/api'
import type { StatsResponse, SignalItem } from '../types/api'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, sig] = await Promise.all([
        fetchStats(),
        fetchSignals({ min_prr: 4.0, min_reports: 10, limit: 10, priority: 'PRIORITY_1' }),
      ])
      setStats(s)
      setSignals(sig.signals)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const fmt = (n: number) => n.toLocaleString()

  return (
    <div className={styles.page}>
      <TopBar
        title="Dashboard"
        subtitle="FDA AEMS/FAERS 2025 Q1 – 2026 Q2 — Pharmacovigilance Overview"
        actions={
          <button className={styles.btn} onClick={() => navigate('/signals')}>
            View All Signals
          </button>
        }
      />

      <div className={styles.content}>
        {error ? (
          <ErrorState message={error} onRetry={load} />
        ) : (
          <>
            <section className={styles.statsGrid} aria-label="Dataset statistics">
              <StatCard
                label="Suspect Reports"
                value={loading ? '—' : fmt(stats?.unique_suspect_reports ?? 0)}
                sub="Unique primary_id reports"
                icon={<Database size={18} />}
                accent
              />
              <StatCard
                label="Active Ingredients"
                value={loading ? '—' : fmt(stats?.unique_active_ingredients ?? 0)}
                sub="Distinct suspect prod_ai"
                icon={<Pill size={18} />}
              />
              <StatCard
                label="Adverse-Event Terms"
                value={loading ? '—' : fmt(stats?.unique_reactions ?? 0)}
                sub="MedDRA Preferred Terms"
                icon={<Heartbeat size={18} />}
              />
              <StatCard
                label="Drug-Event Pairs"
                value={loading ? '—' : fmt(stats?.candidate_drug_event_pairs ?? 0)}
                sub="Candidate signal pairs"
                icon={<LinkSimple size={18} />}
              />
            </section>

            {stats?.reporting_period && (
              <div className={styles.periodBadge}>
                <ShieldWarning size={13} weight="bold" />
                Reporting period: <strong>{stats.reporting_period}</strong>
              </div>
            )}

            <section className={styles.signalSection}>
              <div className={styles.sectionHeader}>
                <h2 className={styles.sectionTitle}>Top Priority-1 Statistical Signals</h2>
                <p className={styles.sectionSub}>
                  PRR ≥ 4.0 · Observed reports (A) ≥ 10 · Background count (C) ≥ 5
                </p>
              </div>
              <SignalTable signals={signals} loading={loading} />
            </section>

            {stats?.disclaimer && (
              <Disclaimer text={stats.disclaimer} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
