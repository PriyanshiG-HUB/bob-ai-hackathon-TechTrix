import type { ModuleScore } from '../types/api'
import styles from './ModuleScoreCard.module.css'

const MODULE_LABELS: Record<string, string> = {
  M1: 'Administrative',
  M2: 'CTD Summaries',
  M3: 'Quality (CMC)',
  M4: 'Nonclinical',
  M5: 'Clinical',
}

interface Props {
  score: ModuleScore
}

export default function ModuleScoreCard({ score }: Props) {
  const pct = score.completeness_percentage
  const isComplete = pct >= 100

  return (
    <div className={`${styles.card} ${isComplete ? styles.complete : ''}`}>
      <div className={styles.header}>
        <div className={styles.moduleId}>{score.module_id}</div>
        <div className={styles.moduleName}>{MODULE_LABELS[score.module_id] ?? score.module_id}</div>
        <div className={`${styles.pct} ${isComplete ? styles.pctComplete : ''}`}>
          {pct.toFixed(0)}%
        </div>
      </div>
      <div className={styles.bar}>
        <div
          className={`${styles.fill} ${isComplete ? styles.fillComplete : ''}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <div className={styles.counts}>
        <span className={styles.present}>{score.present_required_count} present</span>
        {score.missing_required_count > 0 && (
          <span className={styles.missing}>{score.missing_required_count} missing</span>
        )}
      </div>
    </div>
  )
}
