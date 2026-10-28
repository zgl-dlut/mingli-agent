import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { reportApi, type ReportItem } from '../api/report'
import { FollowupReportView } from '../components/FollowupReportView'
import { color, radius } from '../theme/tokens'

export default function ReportDetail() {
  const navigate = useNavigate()
  const { reportId } = useParams<{ reportId: string }>()
  const id = Number(reportId)
  const [report, setReport] = useState<ReportItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!id) return
    try {
      const { data } = await reportApi.get(id)
      setReport(data)
      setError(null)
    } catch (requestError: any) {
      const data = requestError?.response?.data
      if (data?.code === 'entitlement_required') {
        navigate(`/subscription?required=${data.required_plan || 'light'}`, { replace: true })
        return
      }
      setError(data?.message || data?.detail || '报告加载失败')
    } finally {
      setLoading(false)
    }
  }, [id, navigate])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!report || !['pending', 'generating'].includes(report.status)) return
    const timer = window.setInterval(() => void load(), 5000)
    return () => window.clearInterval(timer)
  }, [load, report])

  return (
    <div className="min-h-full pb-8">
      <div className="sticky top-0 z-10 flex items-center px-3 py-3" style={{ backgroundColor: color.bg }}>
        <button onClick={() => navigate(-1)} aria-label="返回" className="w-8 text-xl" style={{ color: color.ink }}>‹</button>
        <div className="flex-1 text-center text-base font-bold" style={{ color: color.ink }}>{report?.title || '解读报告'}</div>
        <span className="w-8" />
      </div>

      {loading && <div className="py-20 text-center text-sm" style={{ color: color.ink2 }}>加载中…</div>}
      {!loading && error && (
        <div className="px-6 py-20 text-center">
          <p className="text-sm" style={{ color: color.danger }}>{error}</p>
          <button onClick={() => void load()} className="mt-3 px-4 py-2 text-sm" style={{ color: color.brand, backgroundColor: color.brandSoft, borderRadius: radius.pill }}>重试</button>
        </div>
      )}
      {!loading && report && ['pending', 'generating'].includes(report.status) && (
        <div className="px-8 py-20 text-center">
          <div className="mx-auto h-1.5 w-44 overflow-hidden" style={{ backgroundColor: color.track, borderRadius: radius.pill }}>
            <div className="ds-analyzing-bar h-full w-2/5" style={{ backgroundColor: color.brand, borderRadius: radius.pill }} />
          </div>
          <div className="mt-5 text-base font-bold" style={{ color: color.ink }}>AI 正在生成解读</div>
          <p className="mt-2 text-xs leading-6" style={{ color: color.ink2 }}>可以先离开本页，生成任务会继续运行。</p>
        </div>
      )}
      {!loading && report?.status === 'failed' && (
        <div className="px-6 py-20 text-center">
          <div className="text-sm font-semibold" style={{ color: color.danger }}>本次生成未完成</div>
          <p className="mt-2 text-xs" style={{ color: color.ink2 }}>{report.failure_message || '请稍后重新打开对应报告。'}</p>
        </div>
      )}
      {!loading && report?.status === 'ready' && report.content && (
        <div className="px-4">
          <div className="p-4" style={{ backgroundColor: color.card, borderRadius: radius.card }}>
            <FollowupReportView content={JSON.stringify(report.content)} />
          </div>
          <div className="px-2 pt-4 text-[11px] leading-5 text-center" style={{ color: color.ink2 }}>
            AI 生成内容仅用于传统文化体验与自我观察，不构成专业决策建议。
          </div>
        </div>
      )}
    </div>
  )
}
