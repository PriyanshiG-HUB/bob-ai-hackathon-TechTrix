import { useEffect, useState, useRef } from 'react'
import { Funnel, ArrowClockwise } from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import SignalTable from '../components/SignalTable'
import Disclaimer from '../components/Disclaimer'
import ErrorState from '../components/ErrorState'
import { fetchSignals, extractErrorMessage } from '../services/api'
import type { SignalItem, PriorityTier } from '../types/api'
import styles from './Signals.module.css'

const DEFAULT_FILTERS = {
  drug_name: '',
  min_prr: 2.0,
  min_reports: 3,
  priority: '' as PriorityTier | '',
  limit: 50,
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [totalReturned, setTotalReturned] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS })
  const [applied, setApplied] = useState({ ...DEFAULT_FILTERS })
  const disclaimerRef = useRef<string>('')

  const load = async (f = applied) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchSignals({
        drug_name: f.drug_name || undefined,
        min_prr: f.min_prr,
        min_reports: f.min_reports,
        priority: f.priority || undefined,
        limit: f.limit,
      })
      setSignals(res.signals)
      setTotalReturned(res.total_returned)
      if (res.signals[0]?.disclaimer) disclaimerRef.current = res.signals[0].disclaimer
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleApply = () => {
    setApplied({ ...filters })
    load(filters)
  }

  const handleReset = () => {
    setFilters({ ...DEFAULT_FILTERS })
    setApplied({ ...DEFAULT_FILTERS })
    load(DEFAULT_FILTERS)
  }

  return (
    <div className={styles.page}>
      <TopBar
        title="Safety Signals"
        subtitle="Statistical disproportionality signals from FDA AEMS/FAERS 2026 Q1"
        actions={
          <span className={styles.count}>
            {loading ? '…' : `${totalReturned.toLocaleString()} signals`}
          </span>
        }
      />

      <div className={styles.content}>
        {/* Filter Bar */}
        <div className={styles.filters} aria-label="Signal filters">
          <div className={styles.filterRow}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="drug-filter">Drug / Active Ingredient</label>
              <input
                id="drug-filter"
                className={styles.input}
                type="text"
                placeholder="e.g. ASPIRIN"
                value={filters.drug_name}
                onChange={e => setFilters(f => ({ ...f, drug_name: e.target.value.toUpperCase() }))}
                onKeyDown={e => e.key === 'Enter' && handleApply()}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="prr-filter">Min PRR</label>
              <input
                id="prr-filter"
                className={styles.input}
                type="number"
                min={0}
                step={0.5}
                value={filters.min_prr}
                onChange={e => setFilters(f => ({ ...f, min_prr: parseFloat(e.target.value) || 0 }))}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="reports-filter">Min Reports (A)</label>
              <input
                id="reports-filter"
                className={styles.input}
                type="number"
                min={1}
                step={1}
                value={filters.min_reports}
                onChange={e => setFilters(f => ({ ...f, min_reports: parseInt(e.target.value) || 1 }))}
              />
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="priority-filter">Priority</label>
              <select
                id="priority-filter"
                className={styles.select}
                value={filters.priority}
                onChange={e => setFilters(f => ({ ...f, priority: e.target.value as PriorityTier | '' }))}
              >
                <option value="">All</option>
                <option value="PRIORITY_1">Priority 1</option>
                <option value="PRIORITY_2">Priority 2</option>
                <option value="REVIEW">Review</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <div className={styles.field}>
              <label className={styles.label} htmlFor="limit-filter">Limit</label>
              <select
                id="limit-filter"
                className={styles.select}
                value={filters.limit}
                onChange={e => setFilters(f => ({ ...f, limit: parseInt(e.target.value) }))}
              >
                {[25, 50, 100, 200, 500].map(v => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>

            <div className={styles.filterActions}>
              <button className={styles.applyBtn} onClick={handleApply}>
                <Funnel size={14} weight="bold" />
                Apply
              </button>
              <button className={styles.resetBtn} onClick={handleReset} title="Reset filters">
                <ArrowClockwise size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Disclaimer note */}
        <div className={styles.noteBox}>
          These are application-level prioritization tiers, not FDA regulatory classifications.
        </div>

        {/* Table */}
        {error
          ? <ErrorState message={error} onRetry={() => load()} />
          : <SignalTable signals={signals} loading={loading} />
        }

        {/* Disclaimer */}
        {disclaimerRef.current && !loading && !error && (
          <Disclaimer text={disclaimerRef.current} compact />
        )}
      </div>
    </div>
  )
}
