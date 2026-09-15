// ============================================================
// AetherGuard AI — TypeScript Types
// Mirrors FastAPI Pydantic schemas exactly.
// ============================================================

// ── Health / Stats ──────────────────────────────────────────

export interface HealthResponse {
  status: string
  service: string
  version: string
  data_loaded: boolean
}

export interface StatsResponse {
  reporting_period: string
  unique_suspect_reports: number
  unique_active_ingredients: number
  unique_reactions: number
  candidate_drug_event_pairs: number
  total_normalized_associations: number | null
  suspect_associations: number | null
  disclaimer: string
}

// ── Safety Signals ───────────────────────────────────────────

export type PriorityTier = 'PRIORITY_1' | 'PRIORITY_2' | 'REVIEW' | 'LOW'
export type SignalLevel = 'LOW' | 'MODERATE' | 'HIGH'
export type SignalConfidence = 'LOW' | 'MODERATE' | 'HIGH'

export interface SignalItem {
  drug_name: string
  adverse_event: string
  a: number
  b: number
  c: number
  d: number
  prr: number | null
  chi_square: number | null
  drug_event_rate: number | null
  background_event_rate: number | null
  sparse_background: boolean
  signal_level: SignalLevel
  signal_confidence: SignalConfidence
  priority: PriorityTier
  priority_description: string
  disclaimer: string
}

export interface SignalsResponse {
  total_returned: number
  filters_applied: Record<string, unknown>
  signals: SignalItem[]
}

export interface SignalDetailResponse {
  drug_name: string
  adverse_event: string
  a: number
  b: number
  c: number
  d: number
  observed_reports: number
  drug_event_rate: number | null
  background_event_rate: number | null
  prr: number | null
  chi_square: number | null
  sparse_background: boolean
  signal_level: SignalLevel
  confidence: SignalConfidence
  priority: PriorityTier
  priority_description: string
  interpretation: string
  disclaimer: string
  undefined_reason: string | null
  threshold_met: boolean
}

export interface DrugComparisonResponse {
  adverse_event: string
  drug_a: SignalDetailResponse
  drug_b: SignalDetailResponse
  comparison_note: string
  disclaimer: string
}

// ── CTD Submission ───────────────────────────────────────────

export interface CTDSection {
  section_id: string
  title: string
  is_required: boolean
  matched_dossier_section: string | null
  priority_if_missing: string | null
  importance: string | null
}

export interface ModuleScore {
  module_id: string
  module_name: string
  required_sections_count: number
  present_required_count: number
  missing_required_count: number
  completeness_percentage: number
  present_sections: CTDSection[]
  missing_required_sections: CTDSection[]
}

export interface Gap {
  module_id: string
  section_id: string
  title: string
  priority: string
  reason: string
  is_required: boolean
}

export interface GapSummary {
  total_gaps: number
  critical_gaps: number
  high_gaps: number
  medium_gaps: number
}

export type ReadinessStatus = 'READY' | 'MOSTLY_READY' | 'NEEDS_ATTENTION' | 'NOT_READY'

export interface SubmissionReadinessResponse {
  submission_id: string
  overall_completeness: number
  readiness_status: ReadinessStatus
  readiness_description: string
  total_required_sections: number
  present_required_sections_count: number
  missing_required_sections_count: number
  module_scores: Record<string, ModuleScore>
  gap_summary: GapSummary
  gaps: Gap[]
  present_sections: CTDSection[]
  missing_sections: CTDSection[]
  extracted_sections_count: number
  disclaimer: string
}

export interface GapReportResponse {
  submission_id: string
  filter_priority: string | null
  total_gaps: number
  gap_summary: GapSummary
  gaps: Gap[]
  disclaimer: string
}

// ── Bob AI Chat ──────────────────────────────────────────────

export interface BobChatRequest {
  message: string
}

export interface BobChatResponse {
  response: string
  tool_used: string
  intent: string
  data: Record<string, unknown> | null
  disclaimer: string
}

// ── Signal Filters ───────────────────────────────────────────

export interface SignalFilters {
  drug_name: string
  min_prr: number
  min_reports: number
  priority: PriorityTier | ''
  limit: number
}
