import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import type { ReportType } from '../api/entitlement'
import { usePersonStore } from '../store/personStore'
import { useReportStore } from '../store/reportStore'
import { color, radius } from '../theme/tokens'

const TYPE_LABEL: Record<ReportType, string> = {
  base_report: '基础解读',
  monthly_brief: '月度节律',
  annual_brief: '年度趋势',
  relation_report: '关系视角',
  qa_reading: '问答解读',
}

const STATUS_LABEL = {
  pending: '等待生成',
  generating: '生成中',
  ready: '已完成',
  failed: '生成失败',
} as const

export default function ReportLibrary() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { persons } = usePersonStore()
  const { reports, isLoading, error, fetchReports, importLegacy } = useReportStore()
  const [personId, setPersonId] = useState<number | undefined>(() => {
    const parsed = Number(searchParams.get('person_id'))
    return parsed > 0 ? parsed : undefined
  })

  useEffect(() => {
    void importLegacy().finally(() => fetchReports(personId))
  }, [fetchReports, importLegacy, personId])

  return (
    <div className="px-4 pb-8">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/reading')} aria-label="返回解读" className="text-xl" style={{ color: color.ink }}>‹</button>
          <h1 className="m-0 text-lg font-bold" style={{ color: color.ink }}>报告库</h1>
        </div>
        <select
          value={personId ?? ''}
          onChange={(event) => setPersonId(event.target.value ? Number(event.target.value) : undefined)}
          className="px-3 py-2 text-xs"
          style={{ borderRadius: radius.pill, border: `1px solid ${color.divider}`, color: color.ink }}
        >
          <option value="">全部档案</option>
          {persons.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
        </select>
      </div>

      {isLoading && <div className="py-16 text-center text-sm" style={{ color: color.ink2 }}>正在整理报告…</div>}
      {!isLoading && error && <div className="py-16 text-center text-sm" style={{ color: color.danger }}>{error}</div>}
      {!isLoading && !error && reports.length === 0 && (
        <div className="py-16 text-center">
          <div className="text-sm font-semibold" style={{ color: color.ink }}>还没有报告</div>
          <button onClick={() => navigate('/reading')} className="mt-3 text-sm" style={{ color: color.brand }}>去生成第一份报告</button>
        </div>
      )}

      <div className="space-y-2.5">
        {reports.map((report) => {
          const person = persons.find((item) => item.id === report.primary_person_id)
          const lead = typeof report.preview?.lead === 'string' ? report.preview.lead : null
          return (
            <button
              key={report.report_id}
              onClick={() => navigate(`/reading/reports/${report.report_id}`)}
              className="w-full p-4 text-left"
              style={{ backgroundColor: color.card, borderRadius: radius.card }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-bold" style={{ color: color.ink }}>{report.title || TYPE_LABEL[report.report_type]}</div>
                  <div className="mt-1 text-[11px]" style={{ color: color.ink2 }}>
                    {person?.name || '历史档案'}{report.period_key ? ` · ${report.period_key}` : ''}
                  </div>
                </div>
                <span
                  className="flex-none px-2 py-1 text-[10px]"
                  style={{
                    borderRadius: radius.pill,
                    color: report.status === 'failed' ? color.danger : color.brand,
                    backgroundColor: report.status === 'failed' ? color.dangerSoft : color.brandSoft,
                  }}
                >
                  {STATUS_LABEL[report.status]}
                </span>
              </div>
              {lead && <p className="m-0 mt-2 line-clamp-2 text-xs leading-5" style={{ color: color.ink2 }}>{lead}</p>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
