import { WarningCircle } from '@phosphor-icons/react'
import styles from './ErrorState.module.css'

interface Props {
  message: string
  onRetry?: () => void
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className={styles.container} role="alert">
      <WarningCircle size={28} weight="regular" className={styles.icon} />
      <p className={styles.message}>{message}</p>
      {onRetry && (
        <button className={styles.retry} onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
