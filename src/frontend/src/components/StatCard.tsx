import styles from './StatCard.module.css'
import type { ReactNode } from 'react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: ReactNode
  accent?: boolean
}

export default function StatCard({ label, value, sub, icon, accent }: Props) {
  return (
    <div className={`${styles.card} ${accent ? styles.accent : ''}`}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <div className={styles.body}>
        <div className={styles.label}>{label}</div>
        <div className={styles.value}>{value}</div>
        {sub && <div className={styles.sub}>{sub}</div>}
      </div>
    </div>
  )
}
