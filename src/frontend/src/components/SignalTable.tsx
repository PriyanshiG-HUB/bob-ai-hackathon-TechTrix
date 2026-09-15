import { useNavigate } from 'react-router-dom'
import type { SignalItem } from '../types/api'
import PriorityBadge from './PriorityBadge'
import styles from './SignalTable.module.css'

interface Props {
  signals: SignalItem[]
  loading?: boolean
}

function fmt(n: number | null, decimals = 2) {
  if (n === null || n === undefined) return '—'
  return n.toFixed(decimals)
}

export default function SignalTable({ signals, loading }: Props) {
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead><tr>
            <th>Drug</th><th>Adverse Event</th><th>A</th>
            <th>PRR</th><th>χ²</th><th>Confidence</th><th>Priority</th>
          </tr></thead>
          <tbody>
            {Array.from({ length: 8 }).map((_, i) => (
              <tr key={i} className={styles.skeletonRow}>
                {Array.from({ length: 7 }).map((__, j) => (
                  <td key={j}><div className={styles.skeletonCell} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (signals.length === 0) {
    return (
      <div className={styles.empty}>
        <p>No signals match the current filters. Try adjusting the minimum PRR or report count.</p>
      </div>
    )
  }

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Drug / Active Ingredient</th>
            <th>Adverse Event</th>
            <th className={styles.num}>A</th>
            <th className={styles.num}>PRR</th>
            <th className={styles.num}>Chi-Square</th>
            <th>Confidence</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((sig, i) => (
            <tr
              key={i}
              className={styles.row}
              onClick={() => navigate(`/signals/${encodeURIComponent(sig.drug_name)}/${encodeURIComponent(sig.adverse_event)}`)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') navigate(`/signals/${encodeURIComponent(sig.drug_name)}/${encodeURIComponent(sig.adverse_event)}`)
              }}
              aria-label={`View details for ${sig.drug_name} and ${sig.adverse_event}`}
            >
              <td className={styles.drug}>
                <span className={styles.drugName} title={sig.drug_name}>{sig.drug_name}</span>
              </td>
              <td className={styles.event}>
                <span title={sig.adverse_event}>{sig.adverse_event}</span>
              </td>
              <td className={`${styles.num} ${styles.mono}`}>{sig.a.toLocaleString()}</td>
              <td className={`${styles.num} ${styles.mono} ${styles.prr}`}>{fmt(sig.prr)}</td>
              <td className={`${styles.num} ${styles.mono}`}>{fmt(sig.chi_square, 1)}</td>
              <td>
                <span className={`${styles.conf} ${styles[sig.signal_confidence]}`}>
                  {sig.signal_confidence}
                </span>
              </td>
              <td><PriorityBadge priority={sig.priority} size="sm" /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
