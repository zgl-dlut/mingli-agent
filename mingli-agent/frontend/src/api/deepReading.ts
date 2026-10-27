/**
 * AI 深度解读 API（两段式第二段）
 * 后端路由见 backend/app/api/deep_reading.py（字段全英文 snake_case）
 *
 * 解锁改为后台异步任务：unlock 接口立即返回 generating=true，
 * 正文约3分钟后生成完成写入消息 content.detail，前端轮询/刷新即可看到。
 */
import apiClient from './client'

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
  /** 正文是否正在后台生成中（解锁后立即返回 generating=true） */
  generating: boolean
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

  /** 扣积分解锁正文并启动后台生成（立即返回，不等待正文生成完成） */
  unlock: async (messageId: number): Promise<DeepReadingDetail> => {
    const res = await apiClient.post<DeepReadingDetail>(
      `/deep-reading/${messageId}/unlock`,
      undefined,
      { timeout: 30000 },
    )
    return res.data
  },
}
