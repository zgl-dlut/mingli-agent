import { create } from 'zustand'
import { reportApi, type CreateReportInput, type ReportItem } from '../api/report'

interface ReportState {
  reports: ReportItem[]
  isLoading: boolean
  error: string | null
  fetchReports: (personId?: number) => Promise<void>
  createReport: (input: CreateReportInput) => Promise<ReportItem>
  importLegacy: () => Promise<void>
  clearReports: () => void
}

export const useReportStore = create<ReportState>((set, get) => ({
  reports: [],
  isLoading: false,
  error: null,

  fetchReports: async (personId) => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await reportApi.list({
        person_id: personId,
        page_size: 100,
      })
      set({ reports: data.items, isLoading: false })
    } catch (error: any) {
      set({
        isLoading: false,
        error: error?.response?.data?.message || error?.response?.data?.detail || '报告加载失败',
      })
    }
  },

  createReport: async (input) => {
    const { data } = await reportApi.create(input)
    const reports = [data, ...get().reports.filter((item) => item.report_id !== data.report_id)]
    set({ reports })
    return data
  },

  importLegacy: async () => {
    await reportApi.importLegacy()
  },
  clearReports: () => set({ reports: [], isLoading: false, error: null }),
}))
