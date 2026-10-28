import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ReportType } from '../api/entitlement'
import { useEntitlementStore } from '../store/entitlementStore'
import { usePersonStore } from '../store/personStore'
import { useReportStore } from '../store/reportStore'
import { color, radius, shadow } from '../theme/tokens'

const REPORTS: Array<{
  type: Exclude<ReportType, 'qa_reading'>
  title: string
  summary: string
  accent: string
}> = [
  { type: 'base_report', title: '基础解读', summary: '性格底色、优势与成长方向', accent: color.brand },
  { type: 'monthly_brief', title: '本月节律', summary: '阶段重点、行动建议与压力提醒', accent: '#347B68' },
  { type: 'annual_brief', title: '年度趋势', summary: '全年节奏与关键阶段，仅全享可用', accent: color.gold },
  { type: 'relation_report', title: '关系视角', summary: '理解两份档案的互动方式与边界', accent: '#B75C55' },
]

export default function ReadingHome() {
  const navigate = useNavigate()
  const { persons, fetchPersons } = usePersonStore()
  const { entitlement, fetchEntitlement } = useEntitlementStore()
  const { reports, fetchReports, importLegacy, createReport } = useReportStore()
  const [personId, setPersonId] = useState<number | null>(null)
  const [secondaryId, setSecondaryId] = useState<number | null>(null)
  const [busyType, setBusyType] = useState<ReportType | null>(null)

  useEffect(() => {
    void fetchPersons()
    void fetchEntitlement()
  }, [fetchEntitlement, fetchPersons])

  useEffect(() => {
    if (!personId && persons.length) setPersonId(persons[0].id)
  }, [personId, persons])

  useEffect(() => {
    if (!personId) return
    void importLegacy().finally(() => fetchReports(personId))
  }, [fetchReports, importLegacy, personId])

  const otherPersons = useMemo(
    () => persons.filter((person) => person.id !== personId),
    [personId, persons],
  )

  const openReport = async (type: Exclude<ReportType, 'qa_reading'>) => {
    if (!personId) return
    if (!entitlement?.report_access[type]) {
      navigate(`/subscription?required=${type === 'annual_brief' ? 'full' : 'light'}`)
      return
    }
    if (type === 'relation_report' && !secondaryId) {
      alert('请先选择一份关系档案')
      return
    }
    const now = new Date()
    const periodKey =
      type === 'monthly_brief'
        ? `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
        : type === 'annual_brief'
          ? String(now.getFullYear())
          : null
    setBusyType(type)
    try {
      const report = await createReport({
        report_type: type,
        primary_person_id: personId,
        secondary_person_id: type === 'relation_report' ? secondaryId : null,
        period_key: periodKey,
      })
      navigate(`/reading/reports/${report.report_id}`)
    } catch (error: any) {
      const data = error?.response?.data
      if (data?.code === 'entitlement_required') {
        navigate(`/subscription?required=${data.required_plan || 'light'}`)
      } else {
        alert(data?.message || data?.detail || '报告创建失败')
      }
    } finally {
      setBusyType(null)
    }
  }

  if (!persons.length) {
    return (
      <div className="px-4 py-16 text-center">
        <div style={{ color: color.ink, fontWeight: 700 }}>先建立一份出生档案</div>
        <p className="mt-2 text-sm" style={{ color: color.ink2 }}>解读会基于同一份标准化命盘生成。</p>
        <button
          onClick={() => navigate('/')}
          className="mt-5 px-5 py-2.5 text-sm text-white"
          style={{ backgroundColor: color.brand, borderRadius: radius.pill }}
        >
          新建档案
        </button>
      </div>
    )
  }

  return (
    <div className="px-4 pb-8">
      <div className="flex items-end justify-between gap-3 mb-3">
        <div>
          <h1 className="m-0 text-xl font-bold" style={{ color: color.ink }}>解读</h1>
          <p className="m-0 mt-1 text-xs" style={{ color: color.ink2 }}>从命盘依据到可执行建议</p>
        </div>
        <select
          aria-label="选择档案"
          value={personId ?? ''}
          onChange={(event) => setPersonId(Number(event.target.value))}
          className="max-w-[150px] px-3 py-2 text-xs"
          style={{ backgroundColor: color.card, color: color.ink, borderRadius: radius.pill, border: `1px solid ${color.divider}` }}
        >
          {persons.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
        </select>
      </div>

      <button
        onClick={() => navigate(`/chart/${personId}`)}
        className="w-full text-left p-4"
        style={{ borderRadius: radius.card, backgroundColor: color.brand, color: '#fff', boxShadow: shadow.card }}
      >
        <div className="text-xs opacity-75">专业命盘</div>
        <div className="mt-1 text-lg font-bold">查看四柱与运势周期</div>
        <div className="mt-2 text-xs opacity-80">全部报告使用同一命盘快照 ›</div>
      </button>

      <div className="grid grid-cols-2 gap-2.5 mt-3">
        {REPORTS.map((item) => {
          const existing = reports.find((report) => report.report_type === item.type)
          const locked = entitlement && !entitlement.report_access[item.type]
          return (
            <button
              key={item.type}
              onClick={() => void openReport(item.type)}
              disabled={busyType === item.type}
              className="text-left p-3.5 min-h-[126px] disabled:opacity-60"
              style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card }}
            >
              <span className="block w-7 h-1 rounded-full mb-3" style={{ backgroundColor: item.accent }} />
              <span className="block text-sm font-bold" style={{ color: color.ink }}>{item.title}</span>
              <span className="block text-[11px] leading-5 mt-1" style={{ color: color.ink2 }}>{item.summary}</span>
              <span className="block text-[11px] mt-2 font-semibold" style={{ color: locked ? color.gold : item.accent }}>
                {busyType === item.type ? '正在创建…' : locked ? '升级后查看' : existing ? '查看报告 ›' : '生成报告 ›'}
              </span>
            </button>
          )
        })}
      </div>

      {otherPersons.length > 0 && (
        <div className="mt-3 p-3.5" style={{ backgroundColor: color.card, borderRadius: radius.card }}>
          <label className="block text-xs font-semibold mb-2" style={{ color: color.ink }}>关系视角对象</label>
          <select
            value={secondaryId ?? ''}
            onChange={(event) => setSecondaryId(event.target.value ? Number(event.target.value) : null)}
            className="w-full px-3 py-2 text-sm"
            style={{ border: `1px solid ${color.divider}`, borderRadius: '10px', color: color.ink }}
          >
            <option value="">请选择关系档案</option>
            {otherPersons.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
          </select>
        </div>
      )}

      <div className="flex gap-2 mt-3">
        <button
          onClick={() => navigate(`/reading/chat/${personId}`)}
          className="flex-1 py-3 text-sm font-semibold"
          style={{ backgroundColor: color.brandSoft, color: color.brand, borderRadius: '10px' }}
        >
          向解盘 AI 提问
        </button>
        <button
          onClick={() => navigate(`/reading/reports?person_id=${personId}`)}
          className="flex-1 py-3 text-sm font-semibold"
          style={{ backgroundColor: color.card, color: color.ink, borderRadius: '10px', border: `1px solid ${color.divider}` }}
        >
          全部报告
        </button>
      </div>
    </div>
  )
}
