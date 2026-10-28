import apiClient from './client'
import type { ReportType } from './entitlement'

export type ReportStatus = 'pending' | 'generating' | 'ready' | 'failed'

export interface ReportAccess {
  allowed: boolean
  required_plan: 'light' | 'full' | null
}

export interface ReportItem {
  report_id: number
  report_type: ReportType
  status: ReportStatus
  primary_person_id: number
  secondary_person_id: number | null
  period_key: string | null
  title: string
  preview: Record<string, unknown> | null
  content: Record<string, unknown> | null
  chart_snapshot: Record<string, unknown> | null
  prompt_version: string
  source_message_id: number | null
  generated_at: string | null
  failure_code: string | null
  failure_message: string | null
  access: ReportAccess
}

export interface ReportList {
  items: ReportItem[]
  page: number
  page_size: number
  total: number
}

export interface CreateReportInput {
  report_type: Exclude<ReportType, 'qa_reading'>
  primary_person_id: number
  secondary_person_id?: number | null
  period_key?: string | null
}

export const reportApi = {
  list: (params: {
    person_id?: number
    report_type?: ReportType
    status?: ReportStatus
    page?: number
    page_size?: number
  } = {}) => apiClient.get<ReportList>('/reports', { params }),
  create: (data: CreateReportInput) => apiClient.post<ReportItem>('/reports', data),
  get: (reportId: number) => apiClient.get<ReportItem>(`/reports/${reportId}`),
  status: (reportId: number) => apiClient.get<ReportItem>(`/reports/${reportId}/status`),
  importLegacy: () =>
    apiClient.post<{ imported: number; existing: number; scanned: number }>('/reports/import-legacy'),
}
