/**
 * 每日运势 API
 *
 * 字段与后端 `app/api/daily.py` 的 DailyFortuneResponse 一一对应（英文 snake_case）。
 * 枚举 grade 只有三个英文 token，中文展示由页面做映射。
 */
import apiClient from './client'

/** 对外运势等级（禁止扩展为「大吉/大凶」等绝对化等级） */
export type DailyGrade = 'good' | 'neutral' | 'caution'

/** 三段文案：action 零术语 / basis 白话 / chart_ref 术语仅此一行 */
export interface DailyAdvice {
  action: string
  basis: string
  chart_ref: string
}

/** 算法权威基准：chart_ref 中的干支十神必须能在此对账 */
export interface DailyFortuneSource {
  liuri_ganzhi: string
  liuyue_ganzhi: string
  dayun_ganzhi: string
  shishen_tian: string
  shishen_di: string
}

export interface DailyFortune {
  /** YYYY-MM-DD */
  date: string
  advice: DailyAdvice
  source: DailyFortuneSource
  grade: DailyGrade
  yi: string[]
  ji: string[]
  /** 0~100 */
  pressure_level: number
}

export const dailyApi = {
  /** 查询某档案某日运势（date 省略时后端取服务器当日） */
  fortune: (person_id: number, date?: string) =>
    apiClient.get<DailyFortune>('/daily/fortune', {
      params: date ? { person_id, date } : { person_id },
    }),
}

/** 等级中文映射：good→吉 / neutral→平 / caution→慎 */
export const GRADE_LABEL: Record<DailyGrade, string> = {
  good: '吉',
  neutral: '平',
  caution: '慎',
}
