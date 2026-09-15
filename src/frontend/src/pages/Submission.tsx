import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileDashed, CheckCircle } from '@phosphor-icons/react'
import TopBar from '../components/TopBar'
import ModuleScoreCard from '../components/ModuleScoreCard'
import ReadinessBadge from '../components/ReadinessBadge'
import Disclaimer from '../components/Disclaimer'
import ErrorState from '../components/ErrorState'
import { LoadingSpinner } from '../components/LoadingState'
import { checkSubmission, extractErrorMessage } from '../services/api'
import type { SubmissionReadinessResponse } from '../types/api'
import styles from './Submission.module.css'

const SAMPLE_OUTLINE = `1.1 Comprehensive Table of Contents
1.2 Application Form / Administrative Information
1.3 Prescribing Information / Product Labeling
2.1 CTD Table of Contents
2.2 CTD Introduction
2.3 Quality Overall Summary (QOS)
2.4 Nonclinical Overview
2.5 Clinical Overview
2.6 Nonclinical Written and Tabulated Summaries
2.7 Clinical Summary
3.1 Module 3 Table of Contents
3.2.S Drug Substance
3.2.P Drug Product
4.1 Module 4 Table of Contents
4.2.1 Pharmacology
4.2.2 Pharmacokinetics
4.2.3 Toxicology
5.1 Module 5 Table of Contents
5.2 Tabular Listing of All Clinical Studies
5.3.3 Reports of Human PK Studies
5.3.6 Reports of Efficacy and Safety Studies`

export default function SubmissionPage() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [subId, setSubId] = useState('')
  const [result, setResult] = useState<SubmissionReadinessResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleCheck = async () => {
    if (!text.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await checkSubmission(text.trim(), subId.trim() || undefined)
      setResult(res)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleSample = () => {
    setText(SAMPLE_OUTLINE)
  }

  return (
    <div className={styles.page}>
      <TopBar
        title="Submission Readiness"
        subtitle="ICH M4(R4)-based structural CTD completeness checker"
      />

      <div className={styles.content}>
        {/* Input area */}
        <div className={styles.inputCard}>
          <div className={styles.inputHeader}>
            <div>
              <h2 className={styles.inputTitle}>Dossier Outline</h2>
              <p className={styles.inputSub}>Paste your CTD table of contents or section outline below.</p>
            </div>
            <button className={styles.sampleBtn} onClick={handleSample}>
              Load Sample Outline
            </button>
          </div>

          <textarea
            className={styles.textarea}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder={`Paste your dossier outline here, e.g.:\n\n1.1 Table of Contents\n1.2 Application Form\n2.3 Quality Overall Summary\n3.2.S Drug Substance\n…`}
            rows={12}
            spellCheck={false}
          />

          <div className={styles.inputFooter}>
            <div className={styles.idField}>
              <label className={styles.idLabel} htmlFor="sub-id">Submission ID (optional)</label>
              <input
                id="sub-id"
                className={styles.idInput}
                type="text"
                placeholder="e.g. NDA-2026-001"
                value={subId}
                onChange={e => setSubId(e.target.value)}
              />
            </div>
            <button
              className={styles.checkBtn}
              onClick={handleCheck}
              disabled={loading || !text.trim()}
            >
              {loading ? <><LoadingSpinner /> Checking…</> : <><FileDashed size={15} /> Check Completeness</>}
            </button>
          </div>
        </div>

        {error && <ErrorState message={error} />}

        {/* Results */}
        {result && !loading && (
          <>
            {/* Overall readiness */}
            <div className={styles.overallCard}>
              <div className={styles.overallLeft}>
                <CheckCircle size={28} className={styles.overallIcon} weight="fill" />
                <div>
                  <p className={styles.overallLabel}>Overall Completeness</p>
                  <p className={styles.overallPct}>{result.overall_completeness.toFixed(1)}%</p>
                  <p className={styles.overallDesc}>{result.readiness_description}</p>
                </div>
              </div>
              <div className={styles.overallRight}>
                <ReadinessBadge status={result.readiness_status} />
                <div className={styles.overallStats}>
                  <span>{result.present_required_sections_count} / {result.total_required_sections} required sections present</span>
                  {result.missing_required_sections_count > 0 && (
                    <span className={styles.missingCount}>{result.missing_required_sections_count} missing</span>
                  )}
                </div>
                {result.submission_id && (
                  <button
                    className={styles.gapBtn}
                    onClick={() => navigate(`/gaps/${result.submission_id}`)}
                  >
                    View Gap Report
                  </button>
                )}
              </div>
            </div>

            {/* Gap summary */}
            {(result.gap_summary.critical_gaps > 0 || result.gap_summary.high_gaps > 0) && (
              <div className={styles.gapSummaryRow}>
                {result.gap_summary.critical_gaps > 0 && (
                  <div className={`${styles.gapCount} ${styles.gapCritical}`}>
                    <span className={styles.gapNum}>{result.gap_summary.critical_gaps}</span>
                    <span>Critical</span>
                  </div>
                )}
                {result.gap_summary.high_gaps > 0 && (
                  <div className={`${styles.gapCount} ${styles.gapHigh}`}>
                    <span className={styles.gapNum}>{result.gap_summary.high_gaps}</span>
                    <span>High</span>
                  </div>
                )}
                {result.gap_summary.medium_gaps > 0 && (
                  <div className={`${styles.gapCount} ${styles.gapMedium}`}>
                    <span className={styles.gapNum}>{result.gap_summary.medium_gaps}</span>
                    <span>Medium</span>
                  </div>
                )}
              </div>
            )}

            {/* Module cards */}
            <div className={styles.modulesGrid}>
              {Object.values(result.module_scores).map(score => (
                <ModuleScoreCard key={score.module_id} score={score} />
              ))}
            </div>

            <Disclaimer text={result.disclaimer} compact />
          </>
        )}
      </div>
    </div>
  )
}
