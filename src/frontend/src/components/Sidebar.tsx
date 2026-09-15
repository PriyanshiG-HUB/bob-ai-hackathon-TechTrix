import { NavLink, useLocation } from 'react-router-dom'
import {
  ChartBar,
  Flask,
  MagnifyingGlass,
  FileText,
  ListDashes,
  Robot,
} from '@phosphor-icons/react'
import styles from './Sidebar.module.css'

interface NavItem {
  to: string
  label: string
  icon: React.ReactNode
  exact?: boolean
}

const NAV: NavItem[] = [
  { to: '/',           label: 'Dashboard',           icon: <ChartBar size={18} weight="regular" />, exact: true },
  { to: '/signals',    label: 'Safety Signals',       icon: <Flask size={18} weight="regular" /> },
  { to: '/submission', label: 'Submission Readiness', icon: <FileText size={18} weight="regular" /> },
  { to: '/gaps',       label: 'Gap Report',           icon: <ListDashes size={18} weight="regular" /> },
  { to: '/bob',        label: 'Bob AI',               icon: <Robot size={18} weight="regular" /> },
]

export default function Sidebar() {
  const location = useLocation()

  return (
    <aside className={styles.sidebar} aria-label="Primary navigation">
      <div className={styles.brand}>
        <MagnifyingGlass size={20} weight="bold" className={styles.brandIcon} />
        <div className={styles.brandText}>
          <span className={styles.brandName}>AetherGuard AI</span>
          <span className={styles.brandSub}>Pharmacovigilance</span>
        </div>
      </div>

      <nav className={styles.nav}>
        <ul className={styles.navList} role="list">
          {NAV.map(({ to, label, icon, exact }) => {
            const isActive = exact
              ? location.pathname === to
              : location.pathname.startsWith(to)
            return (
              <li key={to}>
                <NavLink
                  to={to}
                  className={`${styles.navItem} ${isActive ? styles.active : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <span className={styles.navIcon}>{icon}</span>
                  <span className={styles.navLabel}>{label}</span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className={styles.footer}>
        <span className={styles.footerBadge}>FDA FAERS 2025 Q1 – 2026 Q2</span>
      </div>
    </aside>
  )
}
