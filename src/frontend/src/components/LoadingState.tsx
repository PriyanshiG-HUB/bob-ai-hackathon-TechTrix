import styles from './LoadingState.module.css'

interface Props {
  message?: string
  rows?: number
}

export function LoadingSpinner() {
  return <div className={styles.spinner} aria-label="Loading" />
}

export function LoadingSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className={styles.skeleton} aria-label="Loading data">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className={styles.row}>
          <div className={`${styles.cell} ${styles.w30}`} />
          <div className={`${styles.cell} ${styles.w50}`} />
          <div className={`${styles.cell} ${styles.w20}`} />
        </div>
      ))}
    </div>
  )
}

export default function LoadingState({ message = 'Loading…' }: Props) {
  return (
    <div className={styles.container}>
      <LoadingSpinner />
      <p className={styles.message}>{message}</p>
    </div>
  )
}
