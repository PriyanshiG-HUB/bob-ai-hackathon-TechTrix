import { useEffect, useState } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import { ArrowLeft } from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import PriorityBadge from '../components/PriorityBadge'
import Disclaimer from '../components/Disclaimer'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { fetchGapReport, extractErrorMessage } from '../services/api'
import type { GapReportResponse, Gap } from '../types/api'
import styles from './GapReport.module.css'

const PRIORITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM']

function GapRow({ gap }: { gap: Gap }) {
  return (
    <div className={`${styles.gapRow} ${styles[gap.priority]}`}>
      <div className={styles.gapMeta}>
        <span className={styles.moduleTag}>{gap.module_id}</span>
        <code className={styles.sectionId}>{gap.section_id}</code>
        <PriorityBadge priority={gap.priority} size="sm" />
      </div>
      <p className={styles.gapTitle}>{gap.title}</p>
      <p className={styles.gapReason}>{gap.reason}</p>
    </div>
  )
}

export default function GapReportPage() {
  const { id } = useParams<{ id: string }>()
  const location = useLocation()
  const [data, setData] = useState<GapReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [priorityFilter, setPriorityFilter] = useState<string>('')

  const submissionId = id ?? (location.state as { submissionId?: string })?.submissionId

  const load = async (pf = priorityFilter) => {
    if (!submissionId) {
      setError('No submission ID provided. Please run a submission check first.')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await fetchGapReport(submissionId, pf || undefined)
      setData(res)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [submissionId]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleFilter = (pf: string) => {
    setPriorityFilter(pf)
    load(pf)
  }

  const grouped: Record<string, Gap[]> = {}
  if (data) {
    for (const p of PRIORITY_ORDER) {
      const items = data.gaps.filter(g => g.priority === p)
      if (items.length > 0) grouped[p] = items
    }
  }

  return (
    <div className={styles.page}>
      <TopBar
        title="Gap Report"
        subtitle={submissionId ? `Submission: ${submissionId}` : 'Missing required CTD sections'}
        actions={
          <Link to="/submission" className={styles.backBtn}>
            <ArrowLeft size={14} />
            Back to Checker
          </Link>
        }
      />

      <div className={styles.content}>
        {loading && <LoadingState message="Loading gap report…" />}
        {error && <ErrorState message={error} />}

        {data && !loading && !error && (
          <>
            {/* Summary bar */}
            <div className={styles.summaryBar}>
              <div className={styles.summaryItem}>
                <span className={styles.summaryNum}>{data.gap_summary.total_gaps}</span>
                <span className={styles.summaryLabel}>Total Gaps</span>
              </div>
              <div className={`${styles.summaryItem} ${styles.critical}`}>
                <span className={styles.summaryNum}>{data.gap_summary.critical_gaps}</span>
                <span className={styles.summaryLabel}>Critical</span>
              </div>
              <div className={`${styles.summaryItem} ${styles.high}`}>
                <span className={styles.summaryNum}>{data.gap_summary.high_gaps}</span>
                <span className={styles.summaryLabel}>High</span>
              </div>
              <div className={`${styles.summaryItem} ${styles.medium}`}>
                <span className={styles.summaryNum}>{data.gap_summary.medium_gaps}</span>
                <span className={styles.summaryLabel}>Medium</span>
              </div>
            </div>

            {/* Priority filter */}
            <div className={styles.filterRow}>
              {['', ...PRIORITY_ORDER].map(p => (
                <button
                  key={p || 'all'}
                  className={`${styles.filterBtn} ${priorityFilter === p ? styles.filterActive : ''}`}
                  onClick={() => handleFilter(p)}
                >
                  {p || 'All'}
                </button>
              ))}
            </div>

            {/* Gaps */}
            {data.gaps.length === 0 ? (
              <div className={styles.noGaps}>
                No gaps found for the current filter.
              </div>
            ) : (
              <div className={styles.gapList}>
                {Object.entries(grouped).map(([priority, gaps]) => (
                  <div key={priority} className={styles.prioritySection}>
                    <h3 className={`${styles.priorityHeading} ${styles[`heading${priority}`]}`}>
                      {priority} ({gaps.length})
                    </h3>
                    {gaps.map((gap, i) => (
                      <GapRow key={i} gap={gap} />
                    ))}
                  </div>
                ))}
              </div>
            )}

            <Disclaimer text={data.disclaimer} compact />
          </>
        )}
      </div>
    </div>
  )
}
