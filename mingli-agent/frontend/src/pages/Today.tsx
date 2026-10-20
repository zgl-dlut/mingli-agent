/**
 * 今日页 —— 今日运势 + 今日建议
 *
 * 视觉严格对齐设计稿 `.trae/documents/ui-design/01-today.html` 的 `#panel-today`：
 * 顶栏（问候/农历/日期）→ 五维切换段 → 总评卡（等级+日主标签+压力条+日柱十神+六维）
 * → 宜忌卡 → 今日建议卡 → 去对话 → 免责声明。
 * 数据来源：GET /api/daily/fortune（契约见 src/api/daily.ts）；配色一律取自 src/theme/tokens。
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dailyApi, GRADE_LABEL } from '../api/daily'
import type { DailyFortune, DailyGrade } from '../api/daily'
import { usePersonStore } from '../store/personStore'
import { solarToLunar } from '../utils/lunarConvert'
import { isApp } from '../utils/platform'
import { color, radius, shadow } from '../theme/tokens'

const LUNAR_MONTHS = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊']
const LUNAR_DAYS = [
  '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
  '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
  '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** 等级徽标底色：good→成功绿 / neutral→主色 / caution→警示橙（禁止升级为「大吉/大凶」） */
const GRADE_BADGE_BG: Record<DailyGrade, string> = {
  good: color.success,
  neutral: color.brand,
  caution: color.warn,
}

/** 五维切换段（设计稿 seg）：本周/本月/本年/人生 待后端就绪，当前仅今日有内容 */
const SEG_TABS = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'year', label: '本年' },
  { key: 'life', label: '人生' },
] as const

type SegKey = (typeof SEG_TABS)[number]['key']

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
  const [seg, setSeg] = useState<SegKey>('today')

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

  /** 设计稿日期格式：9月23日 周三 */
  const dateLabel = useMemo(() => {
    const [y, m, d] = dateStr.split('-').map(Number)
    const wd = WEEKDAYS[new Date(y, m - 1, d).getDay()]
    return `${m}月${d}日 ${wd}`
  }, [dateStr])

  if (persons.length === 0) {
    return (
      <div className="px-4 py-10 text-center">
        <p style={{ color: color.ink2, fontSize: '13px' }} className="mb-4">
          还没有命盘档案，先创建一份才能看今日运势
        </p>
        <button
          onClick={() => navigate('/')}
          className="rounded-full px-5 py-2 text-white text-sm font-medium"
          style={{ backgroundColor: color.brand }}
        >
          去创建档案
        </button>
      </div>
    )
  }

  const grade: DailyGrade = fortune?.grade ?? 'neutral'
  const gradeLabel = GRADE_LABEL[grade] ?? '平'

  return (
    <div className="px-4 pb-4" style={{ paddingTop: '6px' }}>
      {/* 顶栏（设计稿 .topbar） */}
      <div className="flex justify-between items-start" style={{ padding: '0 4px' }}>
        <div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: color.ink }}>
            {greeting()}{currentPerson ? `，${currentPerson.name}` : ''}
          </div>
          <div style={{ fontSize: '12px', color: color.ink2, marginTop: '3px' }}>{lunarText}</div>
        </div>
        <div className="text-right">
          <div style={{ fontSize: '13px', color: color.ink, fontWeight: 500 }}>{dateLabel}</div>
          <div className="flex items-center justify-end gap-2 mt-1">
            {persons.length > 1 && (
              <select
                value={personId ?? ''}
                onChange={(e) => setPersonId(Number(e.target.value))}
                className="rounded-full"
                style={{
                  fontSize: '11px', color: color.ink2, backgroundColor: color.card,
                  border: '1px solid #E4E1DA', padding: '2px 6px',
                }}
              >
                {persons.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            )}
            {personId !== null && isApp() && (
              <button
                onClick={() => navigate(`/chart/${personId}`)}
                className="rounded-full"
                style={{
                  fontSize: '11px', fontWeight: 600, color: color.brand,
                  backgroundColor: color.brandSoft, padding: '3px 9px',
                }}
              >
                看命盘 ›
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 五维切换段（设计稿 .seg） */}
      <div className="flex" style={{ backgroundColor: color.segBg, borderRadius: radius.pill, padding: '3px', margin: '12px 0 6px' }}>
        {SEG_TABS.map((t) => {
          const active = seg === t.key
          return (
            <button
              key={t.key}
              onClick={() => setSeg(t.key)}
              className="flex-1"
              style={{
                padding: '8px 0',
                fontSize: '13px',
                color: active ? color.brand : color.ink2,
                fontWeight: active ? 700 : 400,
                borderRadius: radius.pill,
                backgroundColor: active ? color.card : 'transparent',
                boxShadow: active ? '0 1px 3px rgba(0,0,0,.06)' : 'none',
              }}
            >
              {t.label}
            </button>
          )
        })}
      </div>
      <div className="flex items-center gap-1" style={{ margin: '0 6px 8px', fontSize: '10px', color: color.ink2 }}>
        <span style={{ width: '3px', height: '3px', borderRadius: '50%', backgroundColor: color.gold, flex: 'none' }} />
        本周/本月/本年/人生 可免费预览 · 开通会员看完整版
      </div>

      {seg !== 'today' && (
        <div className="text-center py-16" style={{ fontSize: '13px', color: color.ink2 }}>
          {SEG_TABS.find((t) => t.key === seg)?.label}运势即将上线
        </div>
      )}

      {seg === 'today' && (
        <>
          {isLoading && (
            <div className="text-center py-10" style={{ fontSize: '13px', color: color.ink2 }}>正在推算今日运势…</div>
          )}

          {!isLoading && error && (
            <div className="text-center py-10">
              <p className="mb-3" style={{ color: color.danger, fontSize: '13px' }}>{error}</p>
              <button
                onClick={() => personId !== null && loadFortune(personId)}
                className="rounded-full px-4 py-1.5"
                style={{ backgroundColor: color.brandSoft, color: color.brand, fontSize: '13px' }}
              >
                重试
              </button>
            </div>
          )}

          {!isLoading && !error && fortune && (
            <>
              {/* 总评卡（设计稿 .card.overview） */}
              <div
                style={{
                  backgroundColor: color.card, borderRadius: radius.card, padding: '14px 16px',
                  marginTop: '10px', boxShadow: shadow.card, border: `1.5px solid ${color.brand}`,
                }}
              >
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2" style={{ fontSize: '22px', fontWeight: 800, color: color.ink }}>
                    今日{gradeLabel}
                    <span
                      className="rounded-lg"
                      style={{ fontSize: '12px', fontWeight: 700, color: '#fff', backgroundColor: GRADE_BADGE_BG[grade], padding: '2px 7px' }}
                    >
                      {gradeLabel}
                    </span>
                  </div>
                  {fortune.source.day_master && (
                    <span
                      className="rounded-full"
                      style={{ fontSize: '12px', fontWeight: 600, color: color.brand, backgroundColor: color.brandSoft, padding: '4px 10px' }}
                    >
                      {fortune.source.day_master}日主
                    </span>
                  )}
                </div>

                {/* 压力指数（设计稿 .press-row） */}
                <div className="flex items-center gap-2.5" style={{ marginTop: '14px' }}>
                  <span style={{ fontSize: '12px', color: color.ink2, flex: 'none' }}>压力指数</span>
                  <div className="flex-1 overflow-hidden" style={{ height: '8px', backgroundColor: color.track, borderRadius: radius.pill }}>
                    <div
                      style={{ height: '100%', width: `${fortune.pressure_level}%`, backgroundColor: color.brand, borderRadius: radius.pill }}
                    />
                  </div>
                  <span style={{ fontSize: '15px', fontWeight: 700, color: color.brand, flex: 'none', width: '28px', textAlign: 'right' }}>
                    {fortune.pressure_level}
                  </span>
                </div>

                {/* 日柱 + 十神（设计稿 .gz-row） */}
                <div className="flex items-center gap-2" style={{ marginTop: '10px', fontSize: '13px', color: color.ink2 }}>
                  <span>日柱</span>
                  <b style={{ color: color.ink, fontSize: '15px', letterSpacing: '1px' }}>{fortune.source.liuri_ganzhi}</b>
                  {fortune.source.shishen_tian && (
                    <span
                      className="rounded-full"
                      style={{ fontSize: '11px', color: color.gold, border: `1px solid ${color.gold}`, padding: '1.5px 8px' }}
                    >
                      {fortune.source.shishen_tian}
                    </span>
                  )}
                  {fortune.source.liuyue_ganzhi && (
                    <span style={{ fontSize: '11px' }}>· 流月 {fortune.source.liuyue_ganzhi}</span>
                  )}
                </div>
              </div>

              {/* 宜忌卡（设计稿 .yj-row） */}
              <div
                style={{
                  backgroundColor: color.card, borderRadius: radius.card, padding: '14px 16px',
                  marginTop: '10px', boxShadow: shadow.card,
                }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="flex items-center justify-center"
                    style={{ width: '22px', height: '22px', borderRadius: '7px', fontSize: '13px', fontWeight: 700, color: '#fff', backgroundColor: color.success }}
                  >
                    宜
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {fortune.yi.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full"
                        style={{ fontSize: '13px', fontWeight: 500, color: color.success, backgroundColor: color.successSoft, padding: '5px 14px' }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2" style={{ marginTop: '10px' }}>
                  <span
                    className="flex items-center justify-center"
                    style={{ width: '22px', height: '22px', borderRadius: '7px', fontSize: '13px', fontWeight: 700, color: '#fff', backgroundColor: color.danger }}
                  >
                    忌
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {fortune.ji.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full"
                        style={{ fontSize: '13px', fontWeight: 500, color: color.danger, backgroundColor: color.dangerSoft, padding: '5px 14px' }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* 今日建议卡（设计稿 .card.action） */}
              <div
                style={{
                  backgroundColor: color.card, borderRadius: radius.card, padding: '14px 16px',
                  marginTop: '10px', boxShadow: shadow.card,
                }}
              >
                <div style={{ fontSize: '15px', fontWeight: 700, color: color.ink }}>今日建议</div>
                <p style={{ fontSize: '13px', color: color.ink, lineHeight: 1.7, marginTop: '8px' }}>
                  {fortune.advice.action}
                  <br />
                  <span style={{ color: color.ink2, fontSize: '12px' }}>{fortune.advice.basis}</span>
                </p>
                <div
                  style={{
                    marginTop: '10px', paddingTop: '9px', borderTop: `1px dashed #EDE9E0`,
                    fontSize: '11px', color: color.gold,
                  }}
                >
                  依据：{fortune.advice.chart_ref}
                </div>
              </div>

              {/* 去对话（设计稿 .goto-chat） */}
              {personId !== null && (
                <button
                  onClick={() => navigate(`/chat/${personId}`)}
                  className="w-full flex justify-between items-center"
                  style={{
                    marginTop: '12px', backgroundColor: color.brandSoft, borderRadius: radius.card,
                    padding: '13px 16px', fontSize: '13px', color: color.ink,
                  }}
                >
                  <span>想问更细？</span>
                  <b style={{ color: color.brand, fontWeight: 700 }}>去对话 ›</b>
                </button>
              )}

              <p className="text-center" style={{ fontSize: '11px', color: color.ink2, margin: '14px 0 10px' }}>
                内容由AI生成，仅供自我梳理参考
              </p>
            </>
          )}
        </>
      )}
    </div>
  )
}
