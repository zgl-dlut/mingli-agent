import apiClient from './client'
import type { EntitlementSnapshot, PlanCode, ReportType } from './entitlement'

export interface SubscriptionPlan {
  plan_code: PlanCode
  name: string
  monthly_price_yuan: number
  annual_price_yuan: number
  profile_limit: number | null
  qa_daily_limit: number | null
  persona_session_monthly_limit: number | null
  persona_turn_limit: number
  report_access: Record<ReportType, boolean>
  highlights: string[]
}

export const subscriptionApi = {
  getPlans: () => apiClient.get<SubscriptionPlan[]>('/subscriptions/plans'),
  getCurrent: () => apiClient.get<EntitlementSnapshot>('/subscriptions/current'),
  mockActivate: (planCode: Exclude<PlanCode, 'free'>, billingCycle: 'monthly' | 'annual' = 'monthly') =>
    apiClient.post<{ subscription_id: number; entitlement: EntitlementSnapshot }>(
      '/subscriptions/mock-activate',
      { plan_code: planCode, billing_cycle: billingCycle },
    ),
  mockExpire: () => apiClient.post<EntitlementSnapshot>('/subscriptions/mock-expire'),
}
