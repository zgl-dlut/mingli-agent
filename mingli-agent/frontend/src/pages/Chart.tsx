/**
 * 命盘页 —— 生辰 + 排盘 + 流年/流月/流日
 *
 * 数据来源：GET /api/chart/{personId}（契约见 src/api/chart.ts）
 * 只调 chartApi，禁止混用其他接口的中文键数据，保证本页命名口径统一。
 * 视觉对齐设计稿 `.trae/documents/ui-design/01-today.html` / `09-month.html`，配色一律取自 src/theme/tokens。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { chartApi } from '../api/chart'
import type { ChartData, DayunItem, LiunianItem, LiuriItem, LiuyueItem } from '../api/chart'
import { GRADE_LABEL } from '../api/daily'
import type { DailyGrade } from '../api/daily'
import { genderToText } from '../utils/gender'
import { color, radius, shadow } from '../theme/tokens'

/** 等级配色：仅展示层映射，禁止升级为「大吉/大凶」 */
const GRADE_STYLE: Record<DailyGrade, { text: string; bg: string }> = {
  good: { text: color.success, bg: color.successSoft },
  neutral: { text: color.brand, bg: color.brandSoft },
  caution: { text: color.warn, bg: color.warnSoft },
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
          <div className="text-[11px] mb-1" style={{ color: color.ink2 }}>{count[k] ?? 0}</div>
          <div className="h-14 rounded-md flex items-end" style={{ backgroundColor: color.track }}>
            <div
              className="w-full rounded-md"
              style={{ height: `${((count[k] ?? 0) / max) * 100}%`, backgroundColor: color.gold, minHeight: '3px' }}
            />
          </div>
          <div className="text-xs mt-1" style={{ color: color.ink }}>{k}</div>
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
      <div className="px-4 py-10 text-center">
        <p className="text-sm" style={{ color: color.ink2 }}>档案不存在</p>
      </div>
    )
  }

  const selectedMonthNum = Number(month.split('-')[1] || 1)

  return (
    <div className="px-4 py-4 pb-10">
      {/* 顶栏 */}
      <div className="flex items-center gap-2 py-1 mb-1" style={{ backgroundColor: color.bg }}>
        <button onClick={() => navigate(-1)} className="text-lg leading-none px-1" style={{ color: color.ink }}>
          ‹
        </button>
        <div className="font-bold" style={{ fontSize: 17, color: color.ink }}>我的命盘</div>
      </div>

      {isLoading && !data && (
        <div className="text-center text-sm py-12" style={{ color: color.ink2 }}>正在排盘…</div>
      )}

      {!isLoading && error && (
        <div className="text-center py-12">
          <p className="text-sm mb-3" style={{ color: color.danger }}>{error}</p>
          <button
            onClick={() => load(year, month)}
            className="px-4 py-1.5 text-sm"
            style={{ backgroundColor: color.brandSoft, color: color.brand, borderRadius: radius.pill }}
          >
            重试
          </button>
        </div>
      )}

      {data && (
        <>
          {/* 生辰卡 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
              border: `1.5px solid ${color.gold}`,
            }}
          >
            <div className="flex items-center justify-between">
              <div className="font-bold" style={{ fontSize: 18, color: color.ink }}>{data.profile.name}</div>
              <span className="text-xs px-2.5 py-1" style={{ color: color.ink2, backgroundColor: color.bg, borderRadius: radius.pill }}>
                {genderToText(data.profile.gender)} · 属{data.profile.zodiac}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-y-2 mt-3 text-xs">
              <div style={{ color: color.ink2 }}>出生</div>
              <div className="text-right" style={{ color: color.ink }}>
                {data.profile.birth_date} {data.profile.birth_time}
              </div>
              <div style={{ color: color.ink2 }}>历法</div>
              <div className="text-right" style={{ color: color.ink }}>
                {data.profile.calendar_type === 'lunar' ? '农历' : '公历'}
              </div>
              <div style={{ color: color.ink2 }}>出生地</div>
              <div className="text-right" style={{ color: color.ink }}>{data.profile.birth_location || '—'}</div>
              <div style={{ color: color.ink2 }}>真太阳时</div>
              <div className="text-right" style={{ color: color.ink }}>{data.profile.solar_time}</div>
            </div>
          </div>

          {/* 排盘网格 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="mb-3" style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>四柱排盘</div>
            <div className="flex gap-1.5">
              {data.chart.pillars.map((p) => (
                <div key={p.position} className="flex-1 rounded-xl overflow-hidden" style={{ border: `1px solid ${color.divider}` }}>
                  <div className="text-[10px] text-center py-1" style={{ color: color.ink2, backgroundColor: color.bg }}>
                    {PILLAR_LABEL[p.position] ?? p.position}
                  </div>
                  <div className="text-center pt-2">
                    <div className="text-[10px] mb-0.5" style={{ color: color.gold }}>
                      {p.gan_shishen || '—'}
                    </div>
                    <div className="text-2xl font-bold leading-none" style={{ color: color.ink }}>{p.gan}</div>
                    <div className="text-2xl font-bold leading-none mt-1" style={{ color: color.ink }}>{p.zhi}</div>
                  </div>
                  <div className="px-1 pt-2 pb-2 mt-2 space-y-0.5" style={{ borderTop: `1px dashed ${color.divider}` }}>
                    {p.canggan.map((c) => (
                      <div key={c.gan} className="flex items-center justify-center gap-1 text-[10px]" style={{ color: color.ink2 }}>
                        <span className="font-medium" style={{ color: color.ink }}>{c.gan}</span>
                        <span style={{ color: color.gold }}>{c.shishen}</span>
                      </div>
                    ))}
                  </div>
                  <div className="px-1 pb-2 space-y-0.5 text-center" style={{ color: color.ink2 }}>
                    <div className="text-[10px]">{p.nayin}</div>
                    <div className="text-[10px]">{p.changsheng}</div>
                  </div>
                  {p.shensha.length > 0 && (
                    <div className="px-1 pb-2 flex flex-wrap gap-0.5 justify-center">
                      {p.shensha.map((s) => (
                        <span key={s} className="text-[9px] rounded px-1" style={{ color: color.ink2, backgroundColor: color.bg }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <WuxingBar count={data.chart.wuxing_count} />

            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs" style={{ color: color.ink2 }}>
              {data.chart.kongwang.length > 0 && (
                <span>空亡：<b style={{ color: color.ink }}>{data.chart.kongwang.join('、')}</b></span>
              )}
              {data.chart.tiangan_he.length > 0 && (
                <span>天干合：<b style={{ color: color.ink }}>{data.chart.tiangan_he.join('、')}</b></span>
              )}
            </div>
          </div>

          {/* 命理分析 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="mb-3" style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>命理分析</div>
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
                  <span key={k} className="text-xs px-3 py-1" style={{ backgroundColor: color.bg, color: color.ink, borderRadius: radius.pill }}>
                    {k} {v}
                  </span>
                ))}
            </div>
            {data.analysis.tiaohou && (
              <p className="text-xs leading-relaxed mt-3" style={{ color: color.ink2 }}>调候：{data.analysis.tiaohou}</p>
            )}
            {data.analysis.motto && (
              <p
                className="text-sm leading-relaxed mt-3 pt-3 border-t border-dashed"
                style={{ color: color.ink, borderColor: color.divider }}
              >
                {data.analysis.motto}
              </p>
            )}
          </div>

          {/* 大运 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>大运</div>
              <div className="text-xs" style={{ color: color.ink2 }}>
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
                      ? { backgroundColor: color.brand, color: color.card }
                      : { backgroundColor: color.bg, color: color.brand }
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
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>流年</div>
              <div className="text-xs" style={{ color: color.ink2 }}>当前大运十年</div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {data.liunian.map((y: LiunianItem) => {
                const active = y.year === year
                return (
                  <button
                    key={y.year}
                    onClick={() => pickYear(y.year)}
                    className="flex items-center justify-between rounded-xl px-3 py-2 transition-all"
                    style={
                      active
                        ? { backgroundColor: color.brandSoft, border: `1.5px solid ${color.brand}` }
                        : { backgroundColor: color.bg, border: '1.5px solid transparent' }
                    }
                  >
                    <div className="text-left">
                      <div className="text-sm font-bold" style={{ color: color.ink }}>
                        {y.year} <span style={{ color: color.gold }}>{y.ganzhi}</span>
                      </div>
                      <div className="text-[10px]" style={{ color: color.ink2 }}>{y.age !== null ? `${y.age}岁` : ''}</div>
                    </div>
                    <GradeDot grade={y.grade} />
                  </button>
                )
              })}
            </div>
          </div>

          {/* 流月 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>流月</div>
              <div className="text-xs" style={{ color: color.ink2 }}>{year} 年</div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {data.liuyue.map((m: LiuyueItem) => {
                const active = m.solar_month === selectedMonthNum
                return (
                  <button
                    key={m.solar_month}
                    onClick={() => pickMonth(m.solar_month)}
                    className="rounded-xl px-2 py-2 text-center transition-all"
                    style={
                      active
                        ? { backgroundColor: color.brandSoft, border: `1.5px solid ${color.brand}` }
                        : { backgroundColor: color.bg, border: '1.5px solid transparent' }
                    }
                  >
                    <div className="text-xs" style={{ color: color.ink2 }}>{m.solar_month}月</div>
                    <div className="text-sm font-bold tracking-wider" style={{ color: color.ink }}>{m.ganzhi}</div>
                    <div className="flex items-center justify-center gap-1 mt-1">
                      <span className="text-[10px]" style={{ color: color.gold }}>{m.shishen_tian}</span>
                      <GradeDot grade={m.grade} />
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* 流日 */}
          <div
            style={{
              backgroundColor: color.card,
              borderRadius: radius.card,
              padding: '14px 16px',
              marginTop: '10px',
              boxShadow: shadow.card,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontSize: 15, fontWeight: 700, color: color.ink }}>流日</div>
              <div className="text-xs" style={{ color: color.ink2 }}>{year} 年 {selectedMonthNum} 月</div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {data.liuri.map((d: LiuriItem) => (
                <div
                  key={d.date}
                  className="flex items-center justify-between rounded-xl px-3 py-2"
                  style={{ backgroundColor: color.bg }}
                >
                  <div className="text-left">
                    <div className="text-xs font-bold tracking-wider" style={{ color: color.ink }}>{d.ganzhi}</div>
                    <div className="text-[10px]" style={{ color: color.ink2 }}>
                      {Number(d.date.split('-')[2])}日 · {d.shishen_tian || '—'}
                    </div>
                  </div>
                  <GradeDot grade={d.grade} />
                </div>
              ))}
            </div>
          </div>

          <p className="text-center text-xs mt-4" style={{ color: color.ink2 }}>命盘数据由算法排布，仅供自我参照</p>
        </>
      )}
    </div>
  )
}
