/**
 * AI 深度解读 API（两段式第二段）
 * 后端路由见 backend/app/api/deep_reading.py（字段全英文 snake_case）
 */
import apiClient from './client'

/** 解锁正文为同步生成整篇报告，耗时可达 1~2 分钟，需覆盖 apiClient 的 30s 默认超时 */
const UNLOCK_TIMEOUT = 300000

export interface OutlineItem {
  title: string
  lead: string
}

export interface DeepReadingDetail {
  message_id: number
  session_id: number
  person_id: number
  person_name: string
  question: string
  verdict: string
  subtopics: OutlineItem[]
  unlocked: boolean
  /** 已解锁时为完整 FollowupReport 对象，否则为 null */
  report: Record<string, unknown> | null
  /** 解锁所需积分 */
  unlock_points: number
}

export const deepReadingApi = {
  /** 查看某条深度解读大纲消息（框架 + 解锁状态 + 正文） */
  get: async (messageId: number): Promise<DeepReadingDetail> => {
    const res = await apiClient.get<DeepReadingDetail>(`/deep-reading/${messageId}`)
    return res.data
  },

  /** 修改大纲（仅未解锁时允许） */
  updateOutline: async (messageId: number, subtopics: OutlineItem[]): Promise<DeepReadingDetail> => {
    const res = await apiClient.patch<DeepReadingDetail>(`/deep-reading/${messageId}`, { subtopics })
    return res.data
  },

  /** 扣积分解锁正文（幂等：已解锁直接返回，不重复扣费） */
  unlock: async (messageId: number): Promise<DeepReadingDetail> => {
    const res = await apiClient.post<DeepReadingDetail>(
      `/deep-reading/${messageId}/unlock`,
      undefined,
      { timeout: UNLOCK_TIMEOUT },
    )
    return res.data
  },
}
