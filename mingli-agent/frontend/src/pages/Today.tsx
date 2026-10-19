/**
 * 今日页 —— 今日运势 + 今日建议
 *
 * 数据来源：GET /api/daily/fortune（契约见 src/api/daily.ts）
 * 文案口径：《今日建议文案口径Spec》方案 B —— 主句零术语 / 依据句白话 / 依据行带命理依据
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dailyApi, GRADE_LABEL } from '../api/daily'
import type { DailyFortune } from '../api/daily'
import { usePersonStore } from '../store/personStore'
import { solarToLunar } from '../utils/lunarConvert'
import { isApp } from '../utils/platform'

const LUNAR_MONTHS = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊']
const LUNAR_DAYS = [
  '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
  '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
  '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]

/** 等级配色：仅展示层映射，禁止升级为「大吉/大凶」 */
const GRADE_STYLE: Record<string, { text: string; bg: string }> = {
  good: { text: '#2E9E6B', bg: '#E7F4EE' },
  neutral: { text: '#4A4E8F', bg: '#EEEFF9' },
  caution: { text: '#D9772B', bg: '#FBEEDD' },
}

function todayIso(): string {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function greeting(): string {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早安'
  if (h < 18) return '午安'
  return '晚安'
}

export default function Today() {
  const navigate = useNavigate()
  const { persons, fetchPersons } = usePersonStore()

  const [personId, setPersonId] = useState<number | null>(null)
  const [fortune, setFortune] = useState<DailyFortune | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dateStr = useMemo(todayIso, [])

  useEffect(() => {
    if (persons.length === 0) fetchPersons()
  }, [persons.length, fetchPersons])

  // 默认选中第一个档案
  useEffect(() => {
    if (personId === null && persons.length > 0) {
      setPersonId(persons[0].id)
    }
  }, [persons, personId])

  const loadFortune = useCallback(async (id: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await dailyApi.fortune(id, dateStr)
      setFortune(res.data)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || '运势加载失败，请稍后重试')
      setFortune(null)
    } finally {
      setIsLoading(false)
    }
  }, [dateStr])

  useEffect(() => {
    if (personId !== null) loadFortune(personId)
  }, [personId, loadFortune])

  const currentPerson = persons.find((p) => p.id === personId)
  const lunarText = useMemo(() => {
    try {
      const [y, m, d] = dateStr.split('-').map(Number)
      const l = solarToLunar(y, m, d)
      return `农历${l.isLeap ? '闰' : ''}${LUNAR_MONTHS[l.month - 1]}月${LUNAR_DAYS[l.day - 1]}`
    } catch {
      return ''
    }
  }, [dateStr])

  const grade = fortune?.grade ?? 'neutral'
  const gradeStyle = GRADE_STYLE[grade] ?? GRADE_STYLE.neutral
  const gradeLabel = GRADE_LABEL[grade] ?? '平'

  if (persons.length === 0) {
    return (
      <div className="px-4 py-10 text-center" style={{ maxWidth: '640px', margin: '0 auto' }}>
        <p className="text-gray-600 text-sm mb-4">还没有命盘档案，先创建一份才能看今日运势</p>
        <button
          onClick={() => navigate('/')}
          className="rounded-full px-5 py-2 text-white text-sm font-medium"
          style={{ backgroundColor: '#4A4E8F' }}
        >
          去创建档案
        </button>
      </div>
    )
  }

  return (
    <div className="px-4 py-4 pb-8" style={{ maxWidth: '640px', margin: '0 auto' }}>
      {/* 顶栏 */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-lg font-bold text-gray-800">
            {greeting()}{currentPerson ? `，${currentPerson.name}` : ''}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">{lunarText}</div>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-700">{dateStr}</div>
          {persons.length > 1 && (
            <select
              value={personId ?? ''}
              onChange={(e) => setPersonId(Number(e.target.value))}
              className="mt-1 text-xs border rounded-lg px-2 py-1 text-gray-600 bg-white"
            >
              {persons.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
          {personId !== null && isApp() && (
            <button
              onClick={() => navigate(`/chart/${personId}`)}
              className="block ml-auto mt-1 text-xs font-medium rounded-full px-2.5 py-1"
              style={{ color: '#8B6F5A', backgroundColor: '#F5F0E8' }}
            >
              看命盘 ›
            </button>
          )}
        </div>
      </div>

      {isLoading && (
        <div className="text-center text-gray-400 text-sm py-10">正在推算今日运势…</div>
      )}

      {!isLoading && error && (
        <div className="text-center py-10">
          <p className="text-red-500 text-sm mb-3">{error}</p>
          <button
            onClick={() => personId !== null && loadFortune(personId)}
            className="rounded-full px-4 py-1.5 text-sm"
            style={{ backgroundColor: '#EEEFF9', color: '#4A4E8F' }}
          >
            重试
          </button>
        </div>
      )}

      {!isLoading && !error && fortune && (
        <>
          {/* 今日概览 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm" style={{ border: '1.5px solid #4A4E8F' }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-gray-800">今日{gradeLabel}</span>
                <span className="text-xs font-bold text-white rounded-lg px-2 py-0.5" style={{ backgroundColor: gradeStyle.text }}>
                  {gradeLabel}
                </span>
              </div>
              {fortune.source.dayun_ganzhi && (
                <span className="text-xs font-medium rounded-full px-2.5 py-1" style={{ color: '#4A4E8F', backgroundColor: '#EEEFF9' }}>
                  大运 {fortune.source.dayun_ganzhi}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs text-gray-400">压力指数</span>
              <div className="flex-1 h-2 rounded-full" style={{ backgroundColor: '#EFEDE6' }}>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${fortune.pressure_level}%`, backgroundColor: '#4A4E8F' }}
                />
              </div>
              <span className="text-sm font-bold" style={{ color: '#4A4E8F' }}>{fortune.pressure_level}</span>
            </div>

            <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
              <span>流日</span>
              <b className="text-gray-800 text-sm tracking-wider">{fortune.source.liuri_ganzhi}</b>
              {fortune.source.shishen_tian && (
                <span className="rounded-full px-2 py-0.5" style={{ color: '#C9A86A', border: '1px solid #C9A86A' }}>
                  {fortune.source.shishen_tian}
                </span>
              )}
              {fortune.source.liuyue_ganzhi && <span>· 流月 {fortune.source.liuyue_ganzhi}</span>}
            </div>
          </div>

          {/* 今日宜忌 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg text-xs font-bold text-white flex items-center justify-center" style={{ backgroundColor: '#2E9E6B' }}>宜</span>
              <div className="flex flex-wrap gap-2">
                {fortune.yi.map((tag) => (
                  <span key={tag} className="text-xs rounded-full px-3 py-1" style={{ color: '#2E9E6B', backgroundColor: '#E7F4EE' }}>{tag}</span>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <span className="w-6 h-6 rounded-lg text-xs font-bold text-white flex items-center justify-center" style={{ backgroundColor: '#D9534F' }}>忌</span>
              <div className="flex flex-wrap gap-2">
                {fortune.ji.map((tag) => (
                  <span key={tag} className="text-xs rounded-full px-3 py-1" style={{ color: '#D9534F', backgroundColor: '#FBEAE9' }}>{tag}</span>
                ))}
              </div>
            </div>
          </div>

          {/* 今日建议 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="text-sm font-bold text-gray-800">今日建议</div>
            <p className="text-sm text-gray-800 leading-relaxed mt-2">{fortune.advice.action}</p>
            <p className="text-xs text-gray-500 leading-relaxed mt-1">{fortune.advice.basis}</p>
            <div className="text-xs mt-2.5 pt-2 border-t border-dashed" style={{ color: '#C9A86A', borderColor: '#EDE9E0' }}>
              依据：{fortune.advice.chart_ref}
            </div>
          </div>

          {/* 去对话 */}
          {personId !== null && (
            <button
              onClick={() => navigate(`/chat/${personId}`)}
              className="w-full rounded-2xl mt-3 px-4 py-3 flex items-center justify-between text-sm"
              style={{ backgroundColor: '#EEEFF9', color: '#2B2B33' }}
            >
              <span>想问更细？</span>
              <b style={{ color: '#4A4E8F' }}>去对话 ›</b>
            </button>
          )}

          <p className="text-center text-xs text-gray-400 mt-4">内容由AI生成，仅供自我梳理参考</p>
          <p className="text-center text-xs text-gray-400 mt-2">
            运势解读仅供娱乐参考，无法涵盖所有情形，请理性看待，重大决策请以实际情况为准
          </p>
        </>
      )}
    </div>
  )
}
