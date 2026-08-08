/**
 * 对话 API - 支持 SSE 流式输出
 */
import apiClient from './client'
import { createLogger } from '../utils/logger'

const logger = createLogger('chatAPI')

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatSession {
  id: number
  person_id: number
  person_name: string
  title: string
  bazi_data: any
  astro_data: any
  updated_at: string
}

export interface AnalyzeStreamRequest {
  birth_date: string
  birth_time: string
  longitude: number
  latitude: number
  gender: string
  location: string
  bazi_data: any
  is_first_reading: boolean
  question: string
  history: Array<{ role: string; content: string }>
  signal?: AbortSignal
}

export const chatApi = {
  /** 获取会话列表 */
  getSessions: async (): Promise<ChatSession[]> => {
    const res = await apiClient.get<ChatSession[]>('/chat/sessions')
    return res.data
  },

  /** 获取消息历史 */
  getMessages: async (sessionId: number): Promise<ChatMessage[]> => {
    const res = await apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
    return res.data
  },

  /** 发送消息（流式 SSE） */
  sendMessageStream: (sessionId: number, content: string) => {
    const token = localStorage.getItem('mingli_token')
    return fetch(`/api/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ content }),
    })
  },

  /** 获取/生成首次解读（流式 SSE） */
  getFirstReadingStream: (sessionId: number) => {
    const token = localStorage.getItem('mingli_token')
    return fetch(`/api/chat/sessions/${sessionId}/first-reading`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
  },

  /** AI 对话流式接口（无 job_id，旧版，保留兼容） */
  analyzeStream: (data: AnalyzeStreamRequest): Promise<Response> => {
    logger.info(`analyzeStream (legacy)`, { isFirstReading: data.is_first_reading })
    const token = localStorage.getItem('mingli_token')
    const { signal, ...bodyData } = data
    return fetch('/api/chat/analyze-stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(bodyData),
      signal,
    })
  },

  /** AI 对话流式接口（基于 job_id，支持断线重连后拉取结果） */
  analyzeJobStream: (jobId: string, data: AnalyzeStreamRequest): Promise<Response> => {
    logger.info(`analyzeJobStream POST`, { jobId, isFirstReading: data.is_first_reading, questionLen: data.question.length, historyLen: data.history.length })
    const token = localStorage.getItem('mingli_token')
    const { signal, ...bodyData } = data
    return fetch(`/api/chat/analyze-jobs/${encodeURIComponent(jobId)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(bodyData),
      signal,
    })
  },

  /** 查询异步分析任务状态/结果 */
  getAnalyzeJobResult: async (jobId: string): Promise<{ status: string; result: string; error: string }> => {
    logger.info(`getAnalyzeJobResult GET`, { jobId })
    const token = localStorage.getItem('mingli_token')
    const res = await fetch(`/api/chat/analyze-jobs/${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    })
    const data = await res.json()
    logger.debug(`getAnalyzeJobResult 返回`, { jobId, status: data.status, resultLen: data.result?.length || 0 })
    return data
  },

  /** 验证用户问题是否有效（不扣除积分） */
  validateQuestion: async (question: string): Promise<{ valid: boolean; message: string }> => {
    logger.info(`validateQuestion`, { questionLen: question.length, questionPreview: question.slice(0, 30) })
    const token = localStorage.getItem('mingli_token')
    const res = await fetch('/api/chat/validate-question', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ question }),
    })
    return res.json()
  },
}
