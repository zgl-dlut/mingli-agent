import apiClient from './client'

export interface FeatureSnapshot {
  v3_enabled: boolean
  persona_enabled: boolean
  other_persona_enabled: boolean
  points_recharge_enabled: boolean
  subscription_mock_enabled: boolean
}

export const featureApi = {
  get: () => apiClient.get<FeatureSnapshot>('/features'),
}
