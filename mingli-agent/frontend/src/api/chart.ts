/**
 * 命盘 API
 *
 * 字段与后端 `app/api/chart.py` 的 ChartResponse 一一对应（英文 snake_case）。
 * 枚举一律英文 token：position ∈ year/month/day/hour，grade ∈ good/neutral/caution。
 * 命理术语值（干支/十神/五行/纳音/神煞/长生/格局）保持中文，直接来自算法输出。
 */
import apiClient from './client'
import type { DailyGrade } from './daily'

/** 柱位：年/月/日/时 */
export type PillarPosition = 'year' | 'month' | 'day' | 'hour'

export interface ChartProfile {
  name: string
  /** male | female */
  gender: string
  /** YYYY-MM-DD */
  birth_date: string
  /** HH:MM */
  birth_time: string
  birth_location: string
  /** solar | lunar */
  calendar_type: string
  /** 生肖（中文） */
  zodiac: string
  /** 真太阳时校正后的时刻 YYYY-MM-DD HH:MM */
  solar_time: string
}

export interface CangganItem {
  gan: string
  shishen: string
}

export interface Pillar {
  position: PillarPosition
  gan: string
  zhi: string
  /** 十神；日柱为「日主」 */
  gan_shishen: string
  canggan: CangganItem[]
  nayin: string
  changsheng: string
  shensha: string[]
}

export interface ChartGrid {
  pillars: Pillar[]
  /** 五行分布计数，如 { 金: 2, 木: 1 } */
  wuxing_count: Record<string, number>
  kongwang: string[]
  tiangan_he: string[]
}

export interface ChartAnalysis {
  day_master: string
  yueling: string
  wangshuai: string
  geju: string
  yongshen: string
  xishen: string
  jishen: string
  tiaohou: string
  motto: string
}

export interface DayunItem {
  ganzhi: string
  start_year: number
  end_year: number
  start_age: number
  is_current: boolean
}

export interface DayunBlock {
  /** 顺 | 逆 */
  direction: string
  start_age: number
  list: DayunItem[]
}

export interface LiunianItem {
  year: number
  ganzhi: string
  age: number | null
  grade: DailyGrade
  is_yongshen: boolean
  is_jishen: boolean
  interactions: string[]
}

export interface LiuyueItem {
  solar_month: number
  ganzhi: string
  grade: DailyGrade
  is_yongshen: boolean
  is_jishen: boolean
  shishen_tian: string
  shishen_di: string
}

export interface LiuriItem {
  /** YYYY-MM-DD */
  date: string
  ganzhi: string
  shishen_tian: string
  shishen_di: string
  grade: DailyGrade
  is_yongshen: boolean
  is_jishen: boolean
}

export interface ChartData {
  person_id: number
  year: number
  /** YYYY-MM */
  month: string
  profile: ChartProfile
  chart: ChartGrid
  analysis: ChartAnalysis
  dayun: DayunBlock
  liunian: LiunianItem[]
  liuyue: LiuyueItem[]
  liuri: LiuriItem[]
}

export const chartApi = {
  /** 查询某档案的命盘（year/month 省略时后端取当年当月） */
  get: (person_id: number, year?: number, month?: string) =>
    apiClient.get<ChartData>(`/chart/${person_id}`, {
      params: {
        ...(year ? { year } : {}),
        ...(month ? { month } : {}),
      },
    }),
}
