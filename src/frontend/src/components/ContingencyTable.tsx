import styles from './ContingencyTable.module.css'

interface Props {
  a: number
  b: number
  c: number
  d: number
  drugName: string
}

function fmt(n: number) {
  return n.toLocaleString()
}

export default function ContingencyTable({ a, b, c, d, drugName }: Props) {
  const drug = drugName.length > 24 ? drugName.slice(0, 22) + '…' : drugName
  return (
    <div className={styles.wrapper}>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.corner}></th>
              <th className={styles.colHead}>
                <span className={styles.eventLabel}>Target Event</span>
              </th>
              <th className={styles.colHead}>
                <span className={styles.otherLabel}>Other Events</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th className={styles.rowHead}>
                <span className={styles.drugLabel} title={drugName}>{drug}</span>
              </th>
              <td className={styles.cellA}>
                <span className={styles.cellLabel}>A</span>
                <span className={styles.cellValue}>{fmt(a)}</span>
              </td>
              <td className={styles.cellB}>
                <span className={styles.cellLabel}>B</span>
                <span className={styles.cellValue}>{fmt(b)}</span>
              </td>
            </tr>
            <tr>
              <th className={styles.rowHead}>
                <span className={styles.otherDrugLabel}>Other Drugs</span>
              </th>
              <td className={styles.cellC}>
                <span className={styles.cellLabel}>C</span>
                <span className={styles.cellValue}>{fmt(c)}</span>
              </td>
              <td className={styles.cellD}>
                <span className={styles.cellLabel}>D</span>
                <span className={styles.cellValue}>{fmt(d)}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <dl className={styles.legend}>
        <div className={styles.legendItem}>
          <dt className={styles.cellA2}>A</dt>
          <dd>Reports with <strong>{drug}</strong> <em>and</em> the target event</dd>
        </div>
        <div className={styles.legendItem}>
          <dt className={styles.cellB2}>B</dt>
          <dd>Reports with <strong>{drug}</strong> but <em>not</em> the target event</dd>
        </div>
        <div className={styles.legendItem}>
          <dt className={styles.cellC2}>C</dt>
          <dd>Reports with the target event but <em>other drugs</em></dd>
        </div>
        <div className={styles.legendItem}>
          <dt className={styles.cellD2}>D</dt>
          <dd>Reports with neither — background universe</dd>
        </div>
      </dl>
    </div>
  )
}
