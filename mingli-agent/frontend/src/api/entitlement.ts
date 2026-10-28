import apiClient from './client'

export type PlanCode = 'free' | 'light' | 'full'
export type ReportType =
  | 'base_report'
  | 'monthly_brief'
  | 'annual_brief'
  | 'relation_report'
  | 'qa_reading'

export interface UsageAllowance {
  limit: number | null
  used: number
  remaining: number | null
}

export interface EntitlementSnapshot {
  plan_code: PlanCode
  status: string
  expires_at: string | null
  profile: UsageAllowance
  qa_daily: UsageAllowance
  persona_session_monthly: UsageAllowance
  persona_turn_limit: number
  report_access: Record<ReportType, boolean>
}

export const entitlementApi = {
  getMine: () => apiClient.get<EntitlementSnapshot>('/entitlements/me'),
}
