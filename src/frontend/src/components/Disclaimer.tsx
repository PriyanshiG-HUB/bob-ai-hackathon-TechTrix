import { Info } from '@phosphor-icons/react'
import styles from './Disclaimer.module.css'

interface Props {
  text: string
  compact?: boolean
}

export default function Disclaimer({ text, compact }: Props) {
  return (
    <div className={`${styles.disclaimer} ${compact ? styles.compact : ''}`} role="note">
      <Info size={14} weight="regular" className={styles.icon} aria-hidden />
      <p className={styles.text}>{text}</p>
    </div>
  )
}
