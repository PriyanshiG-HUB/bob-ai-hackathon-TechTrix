import Sidebar from './Sidebar'
import styles from './Layout.module.css'

interface Props {
  children: React.ReactNode
}

export default function Layout({ children }: Props) {
  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>
        {children}
      </main>
    </div>
  )
}
