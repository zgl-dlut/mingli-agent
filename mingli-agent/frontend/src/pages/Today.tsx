import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dailyApi, type DailyFortune, type DailyRhythm, type EnergyState } from '../api/daily'
import { usePersonStore } from '../store/personStore'
import { solarToLunar } from '../utils/lunarConvert'
import { color, radius, shadow } from '../theme/tokens'
import { useFeatureStore } from '../store/featureStore'

const LUNAR_MONTHS = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊']
const LUNAR_DAYS = [
  '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
  '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
  '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十',
]
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const STATE_META: Record<EnergyState, { label: string; color: string; background: string }> = {
  smooth: { label: '顺畅', color: '#347B68', background: '#E6F1ED' },
  steady: { label: '平稳', color: color.brand, background: color.brandSoft },
  contracting: { label: '收束', color: '#A06B28', background: '#F8F0DF' },
}

function todayIso(): string {
  const value = new Date()
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早安'
  if (hour < 18) return '午安'
  return '晚安'
}

function legacyFortuneToRhythm(fortune: DailyFortune): DailyRhythm {
  return {
    date: fortune.date,
    energy_state: fortune.grade === 'good' ? 'smooth' : fortune.grade === 'caution' ? 'contracting' : 'steady',
    suitable: fortune.yi,
    notice: fortune.ji,
    action: fortune.advice.action,
    basis: fortune.advice.basis,
    chart_ref: fortune.advice.chart_ref,
    pressure_level: fortune.pressure_level,
    source: fortune.source,
  }
}

export default function Today() {
  const navigate = useNavigate()
  const { persons, fetchPersons } = usePersonStore()
  const { features, fetchFeatures } = useFeatureStore()
  const [personId, setPersonId] = useState<number | null>(null)
  const [rhythm, setRhythm] = useState<DailyRhythm | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const date = useMemo(todayIso, [])

  useEffect(() => {
    void fetchPersons()
    void fetchFeatures()
  }, [fetchFeatures, fetchPersons])

  useEffect(() => {
    if (personId === null && persons.length) setPersonId(persons[0].id)
  }, [personId, persons])

  const load = useCallback(async (id: number) => {
    setLoading(true)
    setError(null)
    try {
      if (features?.v3_enabled === false) {
        const { data } = await dailyApi.fortune(id, date)
        setRhythm(legacyFortuneToRhythm(data))
      } else {
        const { data } = await dailyApi.rhythm(id, date)
        setRhythm(data)
      }
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || '今日节律加载失败')
    } finally {
      setLoading(false)
    }
  }, [date, features?.v3_enabled])

  useEffect(() => {
    if (personId && features) void load(personId)
  }, [features, load, personId])

  const currentPerson = persons.find((person) => person.id === personId)
  const dateText = useMemo(() => {
    const [year, month, day] = date.split('-').map(Number)
    const weekday = WEEKDAYS[new Date(year, month - 1, day).getDay()]
    let lunar = ''
    try {
      const value = solarToLunar(year, month, day)
      lunar = `农历${value.isLeap ? '闰' : ''}${LUNAR_MONTHS[value.month - 1]}月${LUNAR_DAYS[value.day - 1]}`
    } catch {
      lunar = ''
    }
    return { solar: `${month}月${day}日 ${weekday}`, lunar }
  }, [date])

  if (!persons.length) {
    return (
      <div className="px-4 py-16 text-center">
        <div className="text-sm font-semibold" style={{ color: color.ink }}>先建立一份出生档案</div>
        <p className="mt-2 text-xs" style={{ color: color.ink2 }}>有了档案，才能生成你的今日节律。</p>
        <button onClick={() => navigate('/')} className="mt-4 px-5 py-2.5 text-sm text-white" style={{ backgroundColor: color.brand, borderRadius: radius.pill }}>新建档案</button>
      </div>
    )
  }

  const meta = STATE_META[rhythm?.energy_state || 'steady']

  return (
    <div className="px-4 pb-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="m-0 text-xl font-bold" style={{ color: color.ink }}>{greeting()}{currentPerson ? `，${currentPerson.name}` : ''}</h1>
          <div className="mt-1 text-xs" style={{ color: color.ink2 }}>{dateText.lunar}</div>
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold" style={{ color: color.ink }}>{dateText.solar}</div>
          {persons.length > 1 && (
            <select
              value={personId ?? ''}
              onChange={(event) => setPersonId(Number(event.target.value))}
              aria-label="选择档案"
              className="mt-2 max-w-[145px] px-2.5 py-1.5 text-[11px]"
              style={{ color: color.ink, backgroundColor: color.card, border: `1px solid ${color.divider}`, borderRadius: radius.pill }}
            >
              {persons.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
            </select>
          )}
        </div>
      </div>

      {loading && <div className="py-16 text-center text-sm" style={{ color: color.ink2 }}>正在整理今日节律…</div>}
      {!loading && error && (
        <div className="py-16 text-center">
          <p className="text-sm" style={{ color: color.danger }}>{error}</p>
          <button onClick={() => personId && void load(personId)} className="mt-3 px-4 py-2 text-sm" style={{ color: color.brand, backgroundColor: color.brandSoft, borderRadius: radius.pill }}>重试</button>
        </div>
      )}

      {!loading && !error && rhythm && (
        <>
          <section className="mt-4 p-4" style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card, border: `1px solid ${meta.color}` }}>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs" style={{ color: color.ink2 }}>今日能量状态</div>
                <div className="mt-1 text-2xl font-bold" style={{ color: color.ink }}>{meta.label}</div>
              </div>
              <span className="px-3 py-1.5 text-xs font-semibold" style={{ color: meta.color, backgroundColor: meta.background, borderRadius: radius.pill }}>{meta.label}</span>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <span className="text-xs" style={{ color: color.ink2 }}>压力</span>
              <div className="h-2 flex-1 overflow-hidden" style={{ backgroundColor: color.track, borderRadius: radius.pill }}>
                <div className="h-full" style={{ width: `${rhythm.pressure_level}%`, backgroundColor: meta.color, borderRadius: radius.pill }} />
              </div>
              <span className="w-7 text-right text-sm font-bold" style={{ color: meta.color }}>{rhythm.pressure_level}</span>
            </div>
          </section>

          <section className="mt-3 p-4" style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card }}>
            <div className="text-sm font-bold" style={{ color: color.ink }}>今天可以这样安排</div>
            <p className="mt-2 text-sm leading-6" style={{ color: color.ink }}>{rhythm.action}</p>
            <p className="mt-1 text-xs leading-5" style={{ color: color.ink2 }}>{rhythm.basis}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {rhythm.suitable.map((item) => <span key={item} className="px-2.5 py-1 text-xs" style={{ color: '#347B68', backgroundColor: '#E6F1ED', borderRadius: radius.pill }}>{item}</span>)}
            </div>
          </section>

          <section className="mt-3 p-4" style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card }}>
            <div className="text-sm font-bold" style={{ color: color.ink }}>需要留意</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {rhythm.notice.map((item) => <span key={item} className="px-2.5 py-1 text-xs" style={{ color: '#A06B28', backgroundColor: '#F8F0DF', borderRadius: radius.pill }}>{item}</span>)}
            </div>
            <details className="mt-3 text-xs" style={{ color: color.ink2 }}>
              <summary style={{ color: color.brand }}>查看分析依据</summary>
              <div className="mt-2">{rhythm.chart_ref}</div>
            </details>
          </section>

          {features?.v3_enabled ? (
            <>
              <button onClick={() => navigate('/reading')} className="mt-3 w-full p-4 text-left" style={{ backgroundColor: color.brandSoft, borderRadius: radius.card }}>
                <span className="block text-sm font-bold" style={{ color: color.brand }}>继续看本月与深度解读</span>
                <span className="mt-1 block text-xs" style={{ color: color.ink2 }}>进入解读，查看报告或向解盘 AI 提问 ›</span>
              </button>
              <button onClick={() => navigate('/persona')} className="mt-2 w-full p-4 text-left" style={{ backgroundColor: color.card, borderRadius: radius.card }}>
                <span className="block text-sm font-bold" style={{ color: color.ink }}>聊聊此刻的感受</span>
                <span className="mt-1 block text-xs" style={{ color: color.ink2 }}>进入命局人格对话 ›</span>
              </button>
            </>
          ) : (
            <button onClick={() => personId && navigate(`/chat/${personId}`)} className="mt-3 w-full p-4 text-left" style={{ backgroundColor: color.brandSoft, borderRadius: radius.card }}>
              <span className="block text-sm font-bold" style={{ color: color.brand }}>继续向解盘 AI 提问</span>
              <span className="mt-1 block text-xs" style={{ color: color.ink2 }}>进入原有对话 ›</span>
            </button>
          )}
          <p className="mt-4 text-center text-[11px]" style={{ color: color.ink2 }}>AI 生成内容仅用于自我观察，不构成专业建议。</p>
        </>
      )}
    </div>
  )
}
