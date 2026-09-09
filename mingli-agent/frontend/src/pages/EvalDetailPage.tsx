import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { adminApi, type EvalResultDetail, type EvalCaseDetail } from '../api/admin'
import AdminNav from '../components/AdminNav'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from 'recharts'

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function EvalDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<EvalResultDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null)

  useEffect(() => {
    const loadDetail = async () => {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const { data } = await adminApi.evalResultDetail(Number(id))
        setDetail(data)
      } catch (err: any) {
        setError(err?.response?.data?.detail || '加载详情失败')
      } finally {
        setLoading(false)
      }
    }
    loadDetail()
  }, [id])

  const getMatchStatus = (caseItem: EvalCaseDetail) => {
    if (caseItem.match) {
      return {
        label: '✓ 检测通过',
        color: 'bg-green-100 text-green-800 border-green-300',
        description: '预期结果与实际结果一致'
      }
    } else {
      return {
        label: '✗ 检测失败',
        color: 'bg-red-100 text-red-800 border-red-300',
        description: '预期结果与实际结果不一致'
      }
    }
  }

  const getExpectedLabel = (expected: boolean) => {
    return expected ? '预期通过' : '预期失败'
  }

  const getActualLabel = (actual: boolean) => {
    return actual ? '实际通过' : '实际失败'
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNav />
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="text-center py-12">加载中...</div>
        </div>
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNav />
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="text-center py-12 text-red-500">{error || '数据不存在'}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 返回按钮 */}
        <button
          onClick={() => navigate('/admin/eval')}
          className="mb-4 text-blue-600 hover:text-blue-800 text-sm flex items-center gap-1"
        >
          ← 返回评测结果
        </button>

        {/* 概览信息 */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h1 className="text-2xl font-bold mb-4">评测详情</h1>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-500">评测集ID</div>
              <div className="text-lg font-medium">{detail.dataset_id}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">评测时间</div>
              <div className="text-lg font-medium">{formatTime(detail.created_at)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">总用例数</div>
              <div className="text-lg font-medium">{detail.total}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">检测准确率</div>
              <div className={`text-lg font-medium ${detail.match_rate >= 0.8 ? 'text-green-600' : detail.match_rate >= 0.6 ? 'text-yellow-600' : 'text-red-600'}`}>
                {(detail.match_rate * 100).toFixed(1)}% ({detail.match_count}/{detail.total})
              </div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-500">通过</div>
              <div className="text-lg font-medium text-green-600">{detail.passed}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">失败</div>
              <div className="text-lg font-medium text-red-600">{detail.failed}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">通过率</div>
              <div className="text-lg font-medium">{(detail.pass_rate * 100).toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">L2格式完成率</div>
              <div className="text-lg font-medium">
                {detail.format_pass_rate != null ? `${(detail.format_pass_rate * 100).toFixed(1)}%` : '-'}
              </div>
            </div>
          </div>
        </div>

        {/* 详细指标 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* 任务完成率分层 */}
          {detail.task_completion_rate && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">任务完成率（L1-L4）</h2>
              <div className="space-y-3">
                {[
                  { label: 'L1 技术完成', value: detail.task_completion_rate.l1_technical, color: 'bg-blue-500', desc: 'JSON解析 + Pydantic校验' },
                  { label: 'L2 格式完成', value: detail.task_completion_rate.l2_format, color: 'bg-green-500', desc: '结构检查（子问题/block/narrative）' },
                  { label: 'L3 质量完成', value: detail.task_completion_rate.l3_quality, color: 'bg-yellow-500', desc: '叙事检查 + 命盘使用检查' },
                  { label: 'L4 综合完成', value: detail.task_completion_rate.l4_satisfaction, color: 'bg-purple-500', desc: 'L1×L2×L3 全部通过' },
                ].map((item) => (
                  <div key={item.label}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700">{item.label}</span>
                      <span className="font-medium">{(item.value * 100).toFixed(1)}%</span>
                    </div>
                    <div className="text-xs text-gray-500 mb-1">{item.desc}</div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`${item.color} h-2 rounded-full transition-all`}
                        style={{ width: `${item.value * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
                <div className="pt-3 border-t border-gray-200">
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-gray-900">综合完成率</span>
                    <span className="text-blue-600">{(detail.task_completion_rate.overall * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 正确率雷达图 */}
          {detail.accuracy_rate && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">正确率（7维度）</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart
                    data={[
                      { dimension: '排盘', value: detail.accuracy_rate.chart * 100 },
                      { dimension: '结构', value: detail.accuracy_rate.structure * 100 },
                      { dimension: '叙事', value: detail.accuracy_rate.narrative * 100 },
                      { dimension: '逻辑', value: detail.accuracy_rate.logic * 100 },
                      { dimension: '一致性', value: detail.accuracy_rate.consistency * 100 },
                      { dimension: '安全', value: detail.accuracy_rate.safety * 100 },
                    ]}
                  >
                    <PolarGrid />
                    <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12 }} />
                    <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
                    <Radar
                      name="正确率"
                      dataKey="value"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.6}
                    />
                    <Tooltip formatter={(value: any) => `${Number(value).toFixed(1)}%`} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="text-center mt-2">
                <span className="text-sm text-gray-600">综合正确率：</span>
                <span className="text-lg font-semibold text-blue-600">
                  {(detail.accuracy_rate.overall * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )}

          {/* 软性评分 */}
          {detail.soft_score && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">软性评分</h2>
              <div className="space-y-3">
                {[
                  { label: '叙事性', value: detail.soft_score.narrative },
                  { label: '通顺性', value: detail.soft_score.fluency },
                  { label: '故事性', value: detail.soft_score.storytelling },
                  { label: '加粗合理性', value: detail.soft_score.bold_rationality },
                  { label: '术语通俗化', value: detail.soft_score.terminology_popularization },
                ].map((item) => (
                  <div key={item.label} className="flex justify-between items-center">
                    <span className="text-sm text-gray-700">{item.label}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-indigo-500 h-2 rounded-full"
                          style={{ width: `${(item.value / 5) * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right">{item.value.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
                <div className="pt-3 border-t border-gray-200">
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-gray-900">平均分</span>
                    <span className="text-indigo-600">{detail.soft_score.avg.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 违规分布 */}
          {detail.violation_distribution && Object.keys(detail.violation_distribution).length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold mb-4">违规分布</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={Object.entries(detail.violation_distribution).map(([name, value]) => ({
                        name,
                        value,
                      }))}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {Object.entries(detail.violation_distribution).map((_, index) => (
                        <Cell key={`cell-${index}`} fill={['#ef4444', '#f97316', '#eab308', '#84cc16', '#06b6d4'][index % 5]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>

        {/* 用例详情列表 */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold">用例详情</h2>
            <p className="text-sm text-gray-500 mt-1">
              预期结果与实际结果一致 = 检测通过（✓）；预期结果与实际结果不一致 = 检测失败（✗）
            </p>
          </div>
          <div className="divide-y divide-gray-200">
            {detail.detail.map((caseItem, idx) => {
              const matchStatus = getMatchStatus(caseItem)
              return (
                <div key={caseItem.id || idx} className="p-6 hover:bg-gray-50">
                  {/* 用例标题和状态 */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded">
                          {caseItem.id}
                        </span>
                        <span className="text-base font-medium text-gray-900">
                          {caseItem.description}
                        </span>
                      </div>
                      <div className={`inline-block text-xs px-2 py-1 rounded border ${matchStatus.color}`}>
                        {matchStatus.label}
                      </div>
                      <span className="text-xs text-gray-500 ml-2">{matchStatus.description}</span>
                    </div>
                  </div>

                  {/* 预期 vs 实际 */}
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-xs text-gray-500 mb-1">预期结果</div>
                      <div className={`text-sm font-medium ${caseItem.expected_pass ? 'text-green-600' : 'text-red-600'}`}>
                        {getExpectedLabel(caseItem.expected_pass)}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded p-3">
                      <div className="text-xs text-gray-500 mb-1">实际结果</div>
                      <div className={`text-sm font-medium ${caseItem.passed ? 'text-green-600' : 'text-red-600'}`}>
                        {getActualLabel(caseItem.passed)}
                      </div>
                    </div>
                  </div>

                  {/* 违规项逐项对比 */}
                  {((caseItem.expected_violations?.length ?? 0) > 0 || (caseItem.violations?.length ?? 0) > 0) && (
                    <div className="mb-4">
                      <div className="text-sm font-medium text-gray-700 mb-2">
                        违规项对比
                      </div>
                      <div className="space-y-2">
                        {/* 预期违规项 */}
                        {(caseItem.expected_violations ?? []).map((expType, eIdx) => {
                          const detected = (caseItem.violations ?? []).find(v => v.type === expType)
                          return (
                            <div key={eIdx} className={`p-3 rounded border ${
                              detected ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                            }`}>
                              <div className="flex items-center gap-2">
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  detected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                }`}>
                                  {detected ? '✓ 已检测到' : '✗ 未检测到'}
                                </span>
                                <span className="text-sm font-medium">{expType}</span>
                              </div>
                              {detected && detected.detail && (
                                <div className="text-xs text-gray-600 mt-1">{detected.detail}</div>
                              )}
                            </div>
                          )
                        })}
                        
                        {/* 额外检测到的违规项 */}
                        {(caseItem.violations ?? [])
                          .filter(v => !(caseItem.expected_violations ?? []).includes(v.type))
                          .map((v, vIdx) => (
                            <div key={vIdx} className="bg-yellow-50 border border-yellow-200 p-3 rounded">
                              <div className="flex items-center gap-2">
                                <span className="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-800">
                                  ⚠ 额外检测到
                                </span>
                                <span className="text-sm font-medium">{v.type}</span>
                              </div>
                              {v.detail && <div className="text-xs text-gray-600 mt-1">{v.detail}</div>}
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* 查看报告按钮 */}
                  <button
                    onClick={() => setExpandedReportId(expandedReportId === caseItem.id ? null : caseItem.id)}
                    className="mt-2 px-3 py-1.5 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                  >
                    {expandedReportId === caseItem.id ? '收起报告' : '查看报告'}
                  </button>

                  {/* 报告内容展示 */}
                  {expandedReportId === caseItem.id && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                      <h3 className="text-sm font-semibold mb-3">报告内容</h3>
                      <div className="space-y-4">
                        {/* Opening */}
                        {caseItem.report?.opening && (
                          <div className="bg-white p-3 rounded border">
                            <div className="text-xs text-gray-500 mb-1">开篇定论</div>
                            <div className="text-sm">{caseItem.report.opening.lead}</div>
                            <div className="text-sm mt-2 font-medium">{caseItem.report.opening.verdict}</div>
                          </div>
                        )}
                        
                        {/* Subtopics */}
                        {caseItem.report?.subtopics?.map((subtopic: any, sIdx: number) => (
                          <div key={sIdx} className="bg-white p-3 rounded border">
                            <div className="text-sm font-semibold mb-2">{subtopic.title}</div>
                            <div className="space-y-2">
                              {subtopic.blocks?.map((block: any, bIdx: number) => (
                                <div key={bIdx} className="text-sm">
                                  <span className="font-medium">{block.keyword}：</span>
                                  <span>{block.narrative}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                        
                        {/* Summary */}
                        {caseItem.report?.summary && (
                          <div className="bg-white p-3 rounded border">
                            <div className="text-sm font-semibold mb-2">{caseItem.report.summary.title}</div>
                            <div className="space-y-1">
                              {caseItem.report.summary.items?.map((item: any, iIdx: number) => (
                                <div key={iIdx} className="text-sm">
                                  <span className="font-medium">{item.keyword}：</span>
                                  <span>{item.text}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
