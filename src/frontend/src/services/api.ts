// ============================================================
// AetherGuard AI — Central API Client
// All backend calls route through this module.
// VITE_API_BASE_URL configures the base URL.
// ============================================================

import axios, { type AxiosError } from 'axios'
import type {
  HealthResponse,
  StatsResponse,
  SignalsResponse,
  SignalDetailResponse,
  DrugComparisonResponse,
  SubmissionReadinessResponse,
  GapReportResponse,
  SignalFilters,
} from '../types/api'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Error helper ─────────────────────────────────────────────

export function extractErrorMessage(err: unknown): string {
  const axErr = err as AxiosError<{ detail?: string }>
  if (axErr?.response?.data?.detail) return axErr.response.data.detail
  if (axErr?.message) return axErr.message
  return 'An unexpected error occurred. Please try again.'
}

// ── Health / Stats ───────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await apiClient.get<HealthResponse>('/health')
  return res.data
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await apiClient.get<StatsResponse>('/stats')
  return res.data
}

// ── Safety Signals ───────────────────────────────────────────

export async function fetchSignals(filters: Partial<SignalFilters> = {}): Promise<SignalsResponse> {
  const params: Record<string, string | number> = {}
  if (filters.drug_name) params['drug_name'] = filters.drug_name
  if (filters.min_prr !== undefined) params['min_prr'] = filters.min_prr
  if (filters.min_reports !== undefined) params['min_reports'] = filters.min_reports
  if (filters.priority) params['priority'] = filters.priority
  params['limit'] = filters.limit ?? 50
  const res = await apiClient.get<SignalsResponse>('/signals', { params })
  return res.data
}

export async function fetchSignalDetail(drug: string, event: string): Promise<SignalDetailResponse> {
  const res = await apiClient.get<SignalDetailResponse>(
    `/signals/${encodeURIComponent(drug)}/${encodeURIComponent(event)}`
  )
  return res.data
}

export async function fetchCompare(
  drugA: string,
  drugB: string,
  event: string
): Promise<DrugComparisonResponse> {
  const res = await apiClient.get<DrugComparisonResponse>('/compare', {
    params: { drug_a: drugA, drug_b: drugB, event },
  })
  return res.data
}

// ── CTD Submission ───────────────────────────────────────────

export async function checkSubmission(
  dossierText: string,
  submissionId?: string
): Promise<SubmissionReadinessResponse> {
  const res = await apiClient.post<SubmissionReadinessResponse>('/submission/check', {
    dossier_text: dossierText,
    submission_id: submissionId,
  })
  return res.data
}

export async function fetchSubmissionResult(id: string): Promise<SubmissionReadinessResponse> {
  const res = await apiClient.get<SubmissionReadinessResponse>(`/submission/${id}`)
  return res.data
}

export async function fetchGapReport(
  id: string,
  priority?: string
): Promise<GapReportResponse> {
  const params: Record<string, string> = {}
  if (priority) params['priority'] = priority
  const res = await apiClient.get<GapReportResponse>(`/submission/${id}/gaps`, { params })
  return res.data
}

export async function fetchModuleDetail(id: string, module: string) {
  const res = await apiClient.get(`/submission/${id}/modules/${module}`)
  return res.data
}

// ── Bob AI Chat ──────────────────────────────────────────────

export async function bobChat(payload: import('../types/api').BobChatRequest): Promise<import('../types/api').BobChatResponse> {
  const res = await apiClient.post<import('../types/api').BobChatResponse>('/bob/chat', payload)
  return res.data
}
