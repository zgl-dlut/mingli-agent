import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { adminApi, type EvalCompareResult } from '../api/admin'
import AdminNav from '../components/AdminNav'

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

const formatPercent = (rate: number) => {
  return `${(rate * 100).toFixed(1)}%`
}

const formatDelta = (delta: number) => {
  const sign = delta > 0 ? '+' : ''
  const color = delta > 0 ? 'text-green-600' : delta < 0 ? 'text-red-600' : 'text-gray-500'
  return <span className={color}>{sign}{(delta * 100).toFixed(1)}%</span>
}

export default function EvalComparePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const baselineId = searchParams.get('baseline')
  const currentId = searchParams.get('current')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [compareData, setCompareData] = useState<EvalCompareResult | null>(null)

  useEffect(() => {
    if (!baselineId || !currentId) {
      setError('缺少对比参数')
      return
    }

    const loadCompare = async () => {
      setLoading(true)
      setError(null)
      try {
        const { data } = await adminApi.evalCompare(Number(baselineId), Number(currentId))
        setCompareData(data)
      } catch (err: any) {
        setError(err?.response?.data?.detail || '加载对比数据失败')
      } finally {
        setLoading(false)
      }
    }

    loadCompare()
  }, [baselineId, currentId])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNav />
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="text-center text-gray-500 py-12">加载中...</div>
        </div>
      </div>
    )
  }

  if (error || !compareData) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNav />
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="text-center text-red-500 py-12">{error || '加载失败'}</div>
          <div className="text-center">
            <button
              onClick={() => navigate('/admin/eval')}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              返回评测列表
            </button>
          </div>
        </div>
      </div>
    )
  }

  const { baseline, current, delta, case_level, violation_distribution } = compareData

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="mb-6">
          <button
            onClick={() => navigate('/admin/eval')}
            className="text-blue-600 hover:text-blue-700 text-sm"
          >
            ← 返回评测列表
          </button>
        </div>

        <h1 className="text-2xl font-bold mb-6">评测结果对比</h1>

        {/* 总览对比 */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">总览对比</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="border-r border-gray-200 pr-6">
              <div className="text-sm text-gray-500 mb-2">基准版本 (ID: {baseline.id})</div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">通过率：</span>
                <span className="font-semibold">{formatPercent(baseline.pass_rate)}</span>
              </div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">L2格式完成率：</span>
                <span className="font-semibold">{formatPercent(baseline.format_pass_rate)}</span>
              </div>
              {baseline.task_completion_rate && (
                <>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L1技术完成：</span>
                    <span className="font-semibold">{formatPercent(baseline.task_completion_rate.l1_technical)}</span>
                  </div>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L3质量完成：</span>
                    <span className="font-semibold">{formatPercent(baseline.task_completion_rate.l3_quality)}</span>
                  </div>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L4综合完成：</span>
                    <span className="font-semibold">{formatPercent(baseline.task_completion_rate.l4_satisfaction)}</span>
                  </div>
                </>
              )}
              <div className="text-sm text-gray-500 mt-2">
                {baseline.passed}/{baseline.total} 通过
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {formatTime(baseline.created_at)}
              </div>
            </div>

            <div className="border-r border-gray-200 pr-6">
              <div className="text-sm text-gray-500 mb-2">当前版本 (ID: {current.id})</div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">通过率：</span>
                <span className="font-semibold">{formatPercent(current.pass_rate)}</span>
              </div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">L2格式完成率：</span>
                <span className="font-semibold">{formatPercent(current.format_pass_rate)}</span>
              </div>
              {current.task_completion_rate && (
                <>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L1技术完成：</span>
                    <span className="font-semibold">{formatPercent(current.task_completion_rate.l1_technical)}</span>
                  </div>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L3质量完成：</span>
                    <span className="font-semibold">{formatPercent(current.task_completion_rate.l3_quality)}</span>
                  </div>
                  <div className="text-sm mb-1">
                    <span className="text-gray-600">L4综合完成：</span>
                    <span className="font-semibold">{formatPercent(current.task_completion_rate.l4_satisfaction)}</span>
                  </div>
                </>
              )}
              <div className="text-sm text-gray-500 mt-2">
                {current.passed}/{current.total} 通过
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {formatTime(current.created_at)}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-500 mb-2">变化</div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">通过率：</span>
                <span className="font-semibold">{formatDelta(delta.pass_rate)}</span>
              </div>
              <div className="text-sm mb-1">
                <span className="text-gray-600">L2格式完成率：</span>
                <span className="font-semibold">{formatDelta(delta.format_pass_rate)}</span>
              </div>
              {delta.l1_technical != null && (
                <div className="text-sm mb-1">
                  <span className="text-gray-600">L1技术完成：</span>
                  <span className="font-semibold">{formatDelta(delta.l1_technical)}</span>
                </div>
              )}
              {delta.l3_quality != null && (
                <div className="text-sm mb-1">
                  <span className="text-gray-600">L3质量完成：</span>
                  <span className="font-semibold">{formatDelta(delta.l3_quality)}</span>
                </div>
              )}
              {delta.l4_satisfaction != null && (
                <div className="text-sm mb-1">
                  <span className="text-gray-600">L4综合完成：</span>
                  <span className="font-semibold">{formatDelta(delta.l4_satisfaction)}</span>
                </div>
              )}
              <div className="text-sm text-gray-500 mt-2">
                通过数变化：{delta.passed_count > 0 ? '+' : ''}{delta.passed_count}
              </div>
            </div>
          </div>
        </div>

        {/* 用例级变化 */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">用例级变化</h2>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="flex items-center mb-3">
                <span className="inline-block w-3 h-3 bg-green-500 rounded-full mr-2"></span>
                <span className="text-sm font-medium text-gray-700">
                  新增通过 ({case_level.improved_count})
                </span>
              </div>
              {case_level.improved.length > 0 ? (
                <div className="space-y-1">
                  {case_level.improved.map(caseId => (
                    <div key={caseId} className="text-sm text-gray-600 bg-green-50 px-3 py-1 rounded">
                      {caseId}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-400">无</div>
              )}
            </div>

            <div>
              <div className="flex items-center mb-3">
                <span className="inline-block w-3 h-3 bg-red-500 rounded-full mr-2"></span>
                <span className="text-sm font-medium text-gray-700">
                  新增失败 ({case_level.regressed_count})
                </span>
              </div>
              {case_level.regressed.length > 0 ? (
                <div className="space-y-1">
                  {case_level.regressed.map(caseId => (
                    <div key={caseId} className="text-sm text-gray-600 bg-red-50 px-3 py-1 rounded">
                      {caseId}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-gray-400">无</div>
              )}
            </div>
          </div>
        </div>

        {/* 违规分布变化 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">违规分布变化</h2>
          {Object.keys(violation_distribution).length > 0 ? (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">违规类型</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">基准版本</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">当前版本</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">变化</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Object.entries(violation_distribution).map(([type, data]) => (
                  <tr key={type}>
                    <td className="px-4 py-3 text-sm text-gray-900">{type}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{data.baseline}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{data.current}</td>
                    <td className="px-4 py-3 text-sm">
                      {data.delta > 0 ? (
                        <span className="text-red-600">+{data.delta}</span>
                      ) : data.delta < 0 ? (
                        <span className="text-green-600">{data.delta}</span>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center text-gray-400 py-8">无违规数据</div>
          )}
        </div>
      </div>
    </div>
  )
}
