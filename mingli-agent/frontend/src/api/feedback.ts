export interface FeedbackRecord {
  id: number
  person_name: string
  question: string
  answer: string
  answer_preview: string
  skill_tag: string
  tag_label: string
  custom_tags: string[]
  model_score: number | null
  model_reason: string | null
  human_score: number | null
  human_comment: string | null
  model_name: string
  is_first_reading: number
  created_at: string
}

export interface FeedbackStats {
  total: number
  avg_model_score: number
  avg_human_score: number
  scored_count: number
  unscored_count: number
  tags: TagStat[]
  model_score_distribution: ScoreDistItem[]
}

export interface TagStat {
  tag: string
  label: string
  count: number
  avg_model_score: number
  avg_human_score: number
}

export interface ScoreDistItem {
  range: string
  count: number
}

export interface FeedbackListResponse {
  total: number
  items: FeedbackRecord[]
  offset: number
  limit: number
}

export interface SaveFeedbackRequest {
  question: string
  answer: string
  person_name?: string
  model_name?: string
  is_first_reading?: boolean
}

export interface UpdateScoreRequest {
  human_score?: number | null
  human_comment?: string | null
}

export interface TagInfo {
  key: string
  label: string
}

const BASE = '/api/feedback'

export const feedbackApi = {
  /** 保存反馈 */
  create: async (data: SaveFeedbackRequest) => {
    const res = await fetch(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    return res.json()
  },

  /** 查询列表 */
  list: async (params: {
    tag?: string
    min_model_score?: number
    max_model_score?: number
    min_human_score?: number
    max_human_score?: number
    keyword?: string
    offset?: number
    limit?: number
  } = {}) => {
    const qs = new URLSearchParams()
    if (params.tag) qs.set('tag', params.tag)
    if (params.min_model_score !== undefined) qs.set('min_model_score', String(params.min_model_score))
    if (params.max_model_score !== undefined) qs.set('max_model_score', String(params.max_model_score))
    if (params.min_human_score !== undefined) qs.set('min_human_score', String(params.min_human_score))
    if (params.max_human_score !== undefined) qs.set('max_human_score', String(params.max_human_score))
    if (params.keyword) qs.set('keyword', params.keyword)
    if (params.offset) qs.set('offset', String(params.offset))
    if (params.limit) qs.set('limit', String(params.limit))
    const res = await fetch(`${BASE}?${qs.toString()}`)
    return res.json() as Promise<FeedbackListResponse>
  },

  /** 获取详情 */
  get: async (id: number) => {
    const res = await fetch(`${BASE}/${id}`)
    return res.json() as Promise<FeedbackRecord>
  },

  /** 更新人工打分 */
  updateScore: async (id: number, data: UpdateScoreRequest) => {
    const res = await fetch(`${BASE}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    return res.json()
  },

  /** 删除 */
  remove: async (id: number) => {
    const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
    return res.json()
  },

  /** 统计概览 */
  stats: async () => {
    const res = await fetch(`${BASE}/stats/overview`)
    return res.json() as Promise<FeedbackStats>
  },

  /** 获取所有标签 */
  tags: async () => {
    const res = await fetch(`${BASE}/tags/list`)
    return res.json() as Promise<{ tags: TagInfo[] }>
  },

  /** 触发模型自评 */
  triggerModelScore: async (id: number) => {
    const res = await fetch(`${BASE}/${id}/model-score`, { method: 'POST' })
    return res.json()
  },
}