import axios from './client'

export interface AnalyzeRequest {
  birth_date: string
  birth_time: string
  longitude: number
  latitude: number
  gender: 'male' | 'female' | '男' | '女' | string
  location: string
}

export interface AnalyzeResult {
  四柱: string
  日主: string
  月令: string
  旺衰结论: string
  旺衰详情: {
    得令: { score: number; detail: string; description: string }
    得地: { score: number; detail: string; description: string }
    得势: { score: number; detail: string; description: string }
    总分: number
  }
  格局: string
  格局详情: {
    类型: string
    来源: string
    喜忌: { 喜: string; 忌: string; 描述?: string }
  }
  用神: string
  喜神: string
  忌神: string
  调候描述: string
  地支作用: string
  十神分布: string
  五行分布: Record<string, number>
  纳音: Record<string, string>
  当前大运: string
  大运解读: string
  重点流年: Array<{
    year: number
    ganzhi: string
    judge: string
    reason: string
  }>
  五行应用: Record<string, {
    行业: string
    色彩: string
    方向: string
    健康: string
    幸运数字: string
    宝石: string
  }>
  占星数据: Record<string, any>
  生肖: string
  命格箴言?: string
  命格箴言标签?: {
    调候标签: string
    十神做功标签: string
  }
}

function normalizeGender(gender: string): '男' | '女' {
  if (gender === 'female' || gender === '女') return '女'
  return '男'
}

// 调用后端分析 API（无状态，不需要认证）
export async function analyzeBazi(data: AnalyzeRequest): Promise<AnalyzeResult> {
  try {
    const response = await axios.post('/bazi/analyze', {
      ...data,
      gender: normalizeGender(String(data.gender)),
    })
    return response.data
  } catch (error) {
    console.error('命理分析失败:', error)
    throw error
  }
}
