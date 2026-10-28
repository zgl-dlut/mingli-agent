import { create } from 'zustand'
import { entitlementApi, type EntitlementSnapshot } from '../api/entitlement'

interface EntitlementState {
  entitlement: EntitlementSnapshot | null
  isLoading: boolean
  error: string | null
  fetchEntitlement: () => Promise<EntitlementSnapshot>
  setEntitlement: (entitlement: EntitlementSnapshot) => void
  clearEntitlement: () => void
}

export const useEntitlementStore = create<EntitlementState>((set) => ({
  entitlement: null,
  isLoading: false,
  error: null,

  fetchEntitlement: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await entitlementApi.getMine()
      set({ entitlement: data, isLoading: false })
      return data
    } catch (error: any) {
      const message = error?.response?.data?.message || error?.response?.data?.detail || '权益加载失败'
      set({ error: message, isLoading: false })
      throw error
    }
  },

  setEntitlement: (entitlement) => set({ entitlement, error: null }),
  clearEntitlement: () => set({ entitlement: null, error: null, isLoading: false }),
}))
