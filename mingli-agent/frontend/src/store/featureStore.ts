import { create } from 'zustand'
import { featureApi, type FeatureSnapshot } from '../api/features'

interface FeatureState {
  features: FeatureSnapshot | null
  fetchFeatures: () => Promise<FeatureSnapshot>
}

export const useFeatureStore = create<FeatureState>((set) => ({
  features: null,
  fetchFeatures: async () => {
    try {
      const { data } = await featureApi.get()
      set({ features: data })
      return data
    } catch {
      const legacy: FeatureSnapshot = {
        v3_enabled: false,
        persona_enabled: false,
        other_persona_enabled: false,
        points_recharge_enabled: false,
        subscription_mock_enabled: false,
      }
      set({ features: legacy })
      return legacy
    }
  },
}))
