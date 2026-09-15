import type { ReadinessStatus } from '../types/api'
import styles from './ReadinessBadge.module.css'

const META: Record<ReadinessStatus, { label: string; cls: string }> = {
  READY: { label: 'Ready', cls: 'ready' },
  MOSTLY_READY: { label: 'Mostly Ready', cls: 'mostlyReady' },
  NEEDS_ATTENTION: { label: 'Needs Attention', cls: 'needsAttention' },
  NOT_READY: { label: 'Not Ready', cls: 'notReady' },
}

export default function ReadinessBadge({ status }: { status: ReadinessStatus }) {
  const { label, cls } = META[status] ?? { label: status, cls: 'notReady' }
  return <span className={`${styles.badge} ${styles[cls]}`}>{label}</span>
}
