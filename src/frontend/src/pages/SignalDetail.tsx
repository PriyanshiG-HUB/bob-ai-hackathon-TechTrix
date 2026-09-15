import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import PriorityBadge from '../components/PriorityBadge'
import ContingencyTable from '../components/ContingencyTable'
import Disclaimer from '../components/Disclaimer'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { fetchSignalDetail, extractErrorMessage } from '../services/api'
import type { SignalDetailResponse } from '../types/api'
import styles from './SignalDetail.module.css'

function fmt(n: number | null, d = 2) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(d)
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className={styles.row}>
      <dt className={styles.rowLabel}>{label}</dt>
      <dd className={`${styles.rowValue} ${mono ? styles.mono : ''}`}>{value}</dd>
    </div>
  )
}

export default function SignalDetailPage() {
  const { drug, event } = useParams<{ drug: string; event: string }>()
  const [data, setData] = useState<SignalDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    if (!drug || !event) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetchSignalDetail(
        decodeURIComponent(drug),
        decodeURIComponent(event)
      )
      setData(res)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [drug, event]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={styles.page}>
      <TopBar
        title="Signal Detail"
        subtitle={data ? `${data.drug_name}  ·  ${data.adverse_event}` : 'Loading…'}
        actions={
          <Link to="/signals" className={styles.backBtn}>
            <ArrowLeft size={14} />
            Back to Signals
          </Link>
        }
      />

      <div className={styles.content}>
        {loading && <LoadingState message="Loading signal details…" />}
        {error && <ErrorState message={error} onRetry={load} />}

        {data && !loading && !error && (
          <>
            {/* Header card */}
            <div className={styles.headerCard}>
              <div className={styles.headerLeft}>
                <p className={styles.cardLabel}>Active Ingredient</p>
                <h2 className={styles.cardDrug}>{data.drug_name}</h2>
                <p className={styles.cardLabel} style={{ marginTop: 10 }}>Adverse Event</p>
                <h3 className={styles.cardEvent}>{data.adverse_event}</h3>
              </div>
              <div className={styles.headerRight}>
                <PriorityBadge priority={data.priority} />
                <p className={styles.priorityDesc}>{data.priority_description}</p>
              </div>
            </div>

            {/* Stats + contingency */}
            <div className={styles.grid}>
              {/* Key metrics */}
              <div className={styles.metricsCard}>
                <h3 className={styles.cardTitle}>Statistical Metrics</h3>
                <dl className={styles.metricsList}>
                  <Row label="PRR (Proportional Reporting Ratio)" value={fmt(data.prr)} mono />
                  <Row label="Chi-Square (χ²)" value={fmt(data.chi_square, 3)} mono />
                  <Row label="Drug-Event Rate (A/A+B)" value={data.drug_event_rate !== null ? `${(data.drug_event_rate * 100).toFixed(4)}%` : '—'} mono />
                  <Row label="Background Event Rate (C/C+D)" value={data.background_event_rate !== null ? `${(data.background_event_rate * 100).toFixed(4)}%` : '—'} mono />
                  <Row label="Signal Level" value={data.signal_level} />
                  <Row label="Confidence" value={data.confidence} />
                  <Row label="Sparse Background (C < 5)" value={data.sparse_background ? 'Yes — interpret with caution' : 'No'} />
                  <Row label="Threshold Met" value={data.threshold_met ? 'Yes' : 'No'} />
                </dl>
              </div>

              {/* Contingency table */}
              <div className={styles.tableCard}>
                <h3 className={styles.cardTitle}>2×2 Contingency Table</h3>
                <ContingencyTable
                  a={data.a}
                  b={data.b}
                  c={data.c}
                  d={data.d}
                  drugName={data.drug_name}
                />
              </div>
            </div>

            {/* Interpretation */}
            <div className={styles.interpretCard}>
              <h3 className={styles.cardTitle}>Interpretation</h3>
              <p className={styles.interpretText}>{data.interpretation}</p>
              {data.undefined_reason && (
                <p className={styles.undefinedReason}>{data.undefined_reason}</p>
              )}
            </div>

            <Disclaimer text={data.disclaimer} />
          </>
        )}
      </div>
    </div>
  )
}
