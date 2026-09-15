import type { PriorityTier } from '../types/api'
import styles from './PriorityBadge.module.css'

interface Props {
  priority: PriorityTier | string
  size?: 'sm' | 'md'
}

const LABELS: Record<string, string> = {
  PRIORITY_1: 'PRIORITY 1',
  PRIORITY_2: 'PRIORITY 2',
  REVIEW: 'REVIEW',
  LOW: 'LOW',
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  MEDIUM: 'MEDIUM',
}

export default function PriorityBadge({ priority, size = 'md' }: Props) {
  return (
    <span
      className={`${styles.badge} ${styles[priority.replace(/_/g, '')]} ${size === 'sm' ? styles.sm : ''}`}
      aria-label={`Priority: ${priority}`}
    >
      {LABELS[priority] ?? priority}
    </span>
  )
}
