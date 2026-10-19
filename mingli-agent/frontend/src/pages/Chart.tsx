/**
 * 命盘页 —— 生辰 + 排盘 + 流年/流月/流日
 *
 * 数据来源：GET /api/chart/{personId}（契约见 src/api/chart.ts）
 * 只调 chartApi，禁止混用其他接口的中文键数据，保证本页命名口径统一。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { chartApi } from '../api/chart'
import type { ChartData, DayunItem, LiunianItem, LiuriItem, LiuyueItem } from '../api/chart'
import { GRADE_LABEL } from '../api/daily'
import type { DailyGrade } from '../api/daily'
import { genderToText } from '../utils/gender'

/** 等级配色：仅展示层映射，禁止升级为「大吉/大凶」 */
const GRADE_STYLE: Record<DailyGrade, { text: string; bg: string }> = {
  good: { text: '#2E9E6B', bg: '#E7F4EE' },
  neutral: { text: '#4A4E8F', bg: '#EEEFF9' },
  caution: { text: '#D9772B', bg: '#FBEEDD' },
}

const PILLAR_LABEL: Record<string, string> = {
  year: '年柱',
  month: '月柱',
  day: '日柱',
  hour: '时柱',
}

function gradeStyle(g: DailyGrade) {
  return GRADE_STYLE[g] ?? GRADE_STYLE.neutral
}

function GradeDot({ grade }: { grade: DailyGrade }) {
  const s = gradeStyle(grade)
  return (
    <span
      className="inline-flex items-center justify-center rounded-md px-1.5 py-0.5 text-[10px] font-bold"
      style={{ color: s.text, backgroundColor: s.bg }}
    >
      {GRADE_LABEL[grade] ?? '平'}
    </span>
  )
}

/** 五行分布条 */
function WuxingBar({ count }: { count: Record<string, number> }) {
  const order = ['金', '木', '水', '火', '土']
  const max = Math.max(1, ...order.map((k) => count[k] ?? 0))
  return (
    <div className="flex items-end gap-2 mt-3">
      {order.map((k) => (
        <div key={k} className="flex-1 text-center">
          <div className="text-[11px] text-gray-400 mb-1">{count[k] ?? 0}</div>
          <div className="h-14 rounded-md flex items-end" style={{ backgroundColor: '#F3F1EC' }}>
            <div
              className="w-full rounded-md"
              style={{ height: `${((count[k] ?? 0) / max) * 100}%`, backgroundColor: '#C9A86A', minHeight: '3px' }}
            />
          </div>
          <div className="text-xs text-gray-600 mt-1">{k}</div>
        </div>
      ))}
    </div>
  )
}

export default function Chart() {
  const { personId: personIdParam } = useParams()
  const navigate = useNavigate()
  const personId = Number(personIdParam)

  const now = useMemo(() => new Date(), [])
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(
    `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
  )

  const [data, setData] = useState<ChartData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (y: number, m: string) => {
    if (!Number.isFinite(personId) || personId <= 0) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await chartApi.get(personId, y, m)
      setData(res.data)
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail || '命盘加载失败，请稍后重试')
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }, [personId])

  useEffect(() => {
    load(year, month)
  }, [load, year, month])

  /** 切流年：月份跟随到该年同一月 */
  const pickYear = (y: number) => {
    const mm = month.split('-')[1] || '01'
    setYear(y)
    setMonth(`${y}-${mm}`)
  }

  /** 切流月：仅改月份 */
  const pickMonth = (m: number) => {
    setMonth(`${year}-${String(m).padStart(2, '0')}`)
  }

  if (!Number.isFinite(personId) || personId <= 0) {
    return (
      <div className="px-4 py-10 text-center" style={{ maxWidth: '760px', margin: '0 auto' }}>
        <p className="text-gray-600 text-sm">档案不存在</p>
      </div>
    )
  }

  const selectedMonthNum = Number(month.split('-')[1] || 1)

  return (
    <div className="px-4 py-4 pb-10" style={{ maxWidth: '760px', margin: '0 auto' }}>
      {/* 顶栏 */}
      <div className="flex items-center justify-between mb-3">
        <button onClick={() => navigate(-1)} className="text-sm text-gray-500">‹ 返回</button>
        <div className="text-sm font-bold text-gray-800">我的命盘</div>
        <div className="w-10" />
      </div>

      {isLoading && !data && (
        <div className="text-center text-gray-400 text-sm py-12">正在排盘…</div>
      )}

      {!isLoading && error && (
        <div className="text-center py-12">
          <p className="text-red-500 text-sm mb-3">{error}</p>
          <button
            onClick={() => load(year, month)}
            className="rounded-full px-4 py-1.5 text-sm"
            style={{ backgroundColor: '#EEEFF9', color: '#4A4E8F' }}
          >
            重试
          </button>
        </div>
      )}

      {data && (
        <>
          {/* 生辰卡 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm" style={{ border: '1.5px solid #C9A86A' }}>
            <div className="flex items-center justify-between">
              <div className="text-lg font-bold text-gray-800">{data.profile.name}</div>
              <span className="text-xs rounded-full px-2.5 py-1" style={{ color: '#8B6F5A', backgroundColor: '#F5F0E8' }}>
                {genderToText(data.profile.gender)} · 属{data.profile.zodiac}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 mt-3 text-xs">
              <div className="text-gray-400">出生</div>
              <div className="text-gray-700 text-right">
                {data.profile.birth_date} {data.profile.birth_time}
              </div>
              <div className="text-gray-400">历法</div>
              <div className="text-gray-700 text-right">
                {data.profile.calendar_type === 'lunar' ? '农历' : '公历'}
              </div>
              <div className="text-gray-400">出生地</div>
              <div className="text-gray-700 text-right">{data.profile.birth_location || '—'}</div>
              <div className="text-gray-400">真太阳时</div>
              <div className="text-gray-700 text-right">{data.profile.solar_time}</div>
            </div>
          </div>

          {/* 排盘网格 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="text-sm font-bold text-gray-800 mb-3">四柱排盘</div>
            <div className="flex gap-1.5">
              {data.chart.pillars.map((p) => (
                <div key={p.position} className="flex-1 rounded-xl overflow-hidden" style={{ border: '1px solid #EDE9E0' }}>
                  <div className="text-[10px] text-center py-1 text-gray-400" style={{ backgroundColor: '#FAF8F4' }}>
                    {PILLAR_LABEL[p.position] ?? p.position}
                  </div>
                  <div className="text-center pt-2">
                    <div className="text-[10px] mb-0.5" style={{ color: '#C9A86A' }}>
                      {p.gan_shishen || '—'}
                    </div>
                    <div className="text-2xl font-bold text-gray-800 leading-none">{p.gan}</div>
                    <div className="text-2xl font-bold text-gray-800 leading-none mt-1">{p.zhi}</div>
                  </div>
                  <div className="px-1 pt-2 pb-2 mt-2 space-y-0.5" style={{ borderTop: '1px dashed #EDE9E0' }}>
                    {p.canggan.map((c) => (
                      <div key={c.gan} className="flex items-center justify-center gap-1 text-[10px] text-gray-500">
                        <span className="font-medium text-gray-700">{c.gan}</span>
                        <span style={{ color: '#C9A86A' }}>{c.shishen}</span>
                      </div>
                    ))}
                  </div>
                  <div className="px-1 pb-2 space-y-0.5 text-center">
                    <div className="text-[10px] text-gray-400">{p.nayin}</div>
                    <div className="text-[10px] text-gray-400">{p.changsheng}</div>
                  </div>
                  {p.shensha.length > 0 && (
                    <div className="px-1 pb-2 flex flex-wrap gap-0.5 justify-center">
                      {p.shensha.map((s) => (
                        <span key={s} className="text-[9px] rounded px-1" style={{ color: '#8B6F5A', backgroundColor: '#F5F0E8' }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <WuxingBar count={data.chart.wuxing_count} />

            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-gray-500">
              {data.chart.kongwang.length > 0 && (
                <span>空亡：<b className="text-gray-700">{data.chart.kongwang.join('、')}</b></span>
              )}
              {data.chart.tiangan_he.length > 0 && (
                <span>天干合：<b className="text-gray-700">{data.chart.tiangan_he.join('、')}</b></span>
              )}
            </div>
          </div>

          {/* 命理分析 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="text-sm font-bold text-gray-800 mb-3">命理分析</div>
            <div className="flex flex-wrap gap-2">
              {[
                ['日主', data.analysis.day_master],
                ['月令', data.analysis.yueling],
                ['旺衰', data.analysis.wangshuai],
                ['格局', data.analysis.geju],
                ['用神', data.analysis.yongshen],
                ['喜神', data.analysis.xishen],
                ['忌神', data.analysis.jishen],
              ]
                .filter(([, v]) => v)
                .map(([k, v]) => (
                  <span key={k} className="text-xs rounded-full px-3 py-1" style={{ backgroundColor: '#F5F0E8', color: '#5C4B3B' }}>
                    {k} {v}
                  </span>
                ))}
            </div>
            {data.analysis.tiaohou && (
              <p className="text-xs text-gray-500 leading-relaxed mt-3">调候：{data.analysis.tiaohou}</p>
            )}
            {data.analysis.motto && (
              <p className="text-sm text-gray-800 leading-relaxed mt-3 pt-3 border-t border-dashed" style={{ borderColor: '#EDE9E0' }}>
                {data.analysis.motto}
              </p>
            )}
          </div>

          {/* 大运 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-bold text-gray-800">大运</div>
              <div className="text-xs text-gray-400">
                {data.dayun.direction && `${data.dayun.direction}行 · `}起运 {data.dayun.start_age} 岁
              </div>
            </div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {data.dayun.list.map((d: DayunItem) => (
                <button
                  key={`${d.ganzhi}-${d.start_year}`}
                  onClick={() => pickYear(d.start_year)}
                  className="flex-shrink-0 rounded-xl px-3 py-2 text-center transition-all"
                  style={
                    d.is_current
                      ? { backgroundColor: '#4A4E8F', color: '#fff' }
                      : { backgroundColor: '#F7F5F1', color: '#4A4E8F' }
                  }
                >
                  <div className="text-sm font-bold tracking-wider">{d.ganzhi}</div>
                  <div className="text-[10px] mt-0.5" style={{ opacity: 0.8 }}>{d.start_age}岁</div>
                  <div className="text-[9px] mt-0.5" style={{ opacity: 0.6 }}>
                    {d.start_year}-{d.end_year}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 流年 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-bold text-gray-800">流年</div>
              <div className="text-xs text-gray-400">当前大运十年</div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {data.liunian.map((y: LiunianItem) => {
                const active = y.year === year
                return (
                  <button
                    key={y.year}
                    onClick={() => pickYear(y.year)}
                    className="flex items-center justify-between rounded-xl px-3 py-2 transition-all"
                    style={
                      active
                        ? { backgroundColor: '#EEEFF9', border: '1.5px solid #4A4E8F' }
                        : { backgroundColor: '#FAF8F4', border: '1.5px solid transparent' }
                    }
                  >
                    <div className="text-left">
                      <div className="text-sm font-bold text-gray-800">
                        {y.year} <span style={{ color: '#C9A86A' }}>{y.ganzhi}</span>
                      </div>
                      <div className="text-[10px] text-gray-400">{y.age !== null ? `${y.age}岁` : ''}</div>
                    </div>
                    <GradeDot grade={y.grade} />
                  </button>
                )
              })}
            </div>
          </div>

          {/* 流月 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-bold text-gray-800">流月</div>
              <div className="text-xs text-gray-400">{year} 年</div>
            </div>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {data.liuyue.map((m: LiuyueItem) => {
                const active = m.solar_month === selectedMonthNum
                return (
                  <button
                    key={m.solar_month}
                    onClick={() => pickMonth(m.solar_month)}
                    className="rounded-xl px-2 py-2 text-center transition-all"
                    style={
                      active
                        ? { backgroundColor: '#EEEFF9', border: '1.5px solid #4A4E8F' }
                        : { backgroundColor: '#FAF8F4', border: '1.5px solid transparent' }
                    }
                  >
                    <div className="text-xs text-gray-400">{m.solar_month}月</div>
                    <div className="text-sm font-bold text-gray-800 tracking-wider">{m.ganzhi}</div>
                    <div className="flex items-center justify-center gap-1 mt-1">
                      <span className="text-[10px]" style={{ color: '#C9A86A' }}>{m.shishen_tian}</span>
                      <GradeDot grade={m.grade} />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* 流日 */}
          <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-bold text-gray-800">流日</div>
              <div className="text-xs text-gray-400">{year} 年 {selectedMonthNum} 月</div>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {data.liuri.map((d: LiuriItem) => (
                <div
                  key={d.date}
                  className="flex items-center justify-between rounded-xl px-3 py-2"
                  style={{ backgroundColor: '#FAF8F4' }}
                >
                  <div className="text-left">
                    <div className="text-xs font-bold text-gray-800 tracking-wider">{d.ganzhi}</div>
                    <div className="text-[10px] text-gray-400">
                      {Number(d.date.split('-')[2])}日 · {d.shishen_tian || '—'}
                    </div>
                  </div>
                  <GradeDot grade={d.grade} />
                </div>
              ))}
            </div>
          </div>

          <p className="text-center text-xs text-gray-400 mt-4">命盘数据由算法排布，仅供自我参照</p>
        </>
      )}
    </div>
  )
}
