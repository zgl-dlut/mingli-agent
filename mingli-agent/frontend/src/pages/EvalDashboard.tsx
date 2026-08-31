import { useState, useEffect, useCallback } from 'react'
import { adminApi, type EvalResultItem, type TrendPoint, type FailureAnalysis } from '../api/admin'
import AdminNav from '../components/AdminNav'
import { useNavigate } from 'react-router-dom'
import MetricCard from '../components/MetricCard'
import VersionSelector from '../components/VersionSelector'
import EvalMethodology from '../components/EvalMethodology'

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

// 评测类型映射
const EVAL_TYPE_MAP: Record<string, { label: string; color: string }> = {
  report_quality: { label: '报告质量评测', color: '#3b82f6' },
  chart_accuracy: { label: '排盘正确性评测', color: '#10b981' },
  badcase_eval: { label: 'Badcase动态评测', color: '#f59e0b' },
  production_monitor: { label: '生产环境监控', color: '#8b5cf6' },
}

// 数据来源映射：实验室 vs 生产
const LAB_TYPES = new Set(['report_quality', 'chart_accuracy', 'badcase_eval'])
function getSourceLabel(evalType: string): { label: string; color: string } {
  if (evalType === 'production_monitor') return { label: '生产', color: '#8b5cf6' }
  return { label: '实验室', color: '#3b82f6' }
}

export default function EvalDashboard() {
  const navigate = useNavigate()

  // Tab: overview / results / production / dataset
  const [activeTab, setActiveTab] = useState<'overview' | 'results' | 'production' | 'dataset'>('overview')
  const [filterDatasetId, setFilterDatasetId] = useState('')
  const [filterEvalType, setFilterEvalType] = useState('')
  const [filterSource, setFilterSource] = useState('') // '' | 'lab' | 'production'

  // 评测结果列表
  const [items, setItems] = useState<EvalResultItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 版本选择 & 指标卡片
  const [versions, setVersions] = useState<Array<{ id: number; name: string; created_at: string; eval_type?: string }>>([])
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [selectedResult, setSelectedResult] = useState<EvalResultItem | null>(null)
  const [trendMatchRate, setTrendMatchRate] = useState<TrendPoint[]>([])
  const [trendPassRate, setTrendPassRate] = useState<TrendPoint[]>([])
  const [trendFormatRate, setTrendFormatRate] = useState<TrendPoint[]>([])
  const [trendTaskCompletion, setTrendTaskCompletion] = useState<TrendPoint[]>([])

  // 对比选择
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  // 评测集 Tab
  const [datasetLoading, setDatasetLoading] = useState(false)
  const [datasetError, setDatasetError] = useState<string | null>(null)
  const [datasetItems, setDatasetItems] = useState<any[]>([])
  const [datasetTotal, setDatasetTotal] = useState(0)
  const [latestEvalResult, setLatestEvalResult] = useState<EvalResultItem | null>(null)

  // 概览 Tab 数据
  const [overviewError, setOverviewError] = useState<string | null>(null)
  const [latestResult, setLatestResult] = useState<EvalResultItem | null>(null)
  const [typeDistribution, setTypeDistribution] = useState<Array<{ name: string; value: number; color: string }>>([])
  const [allItems, setAllItems] = useState<EvalResultItem[]>([])

  // 生产监控 Tab 数据
  const [productionItems, setProductionItems] = useState<any[]>([])
  const [productionLoading, setProductionLoading] = useState(false)
  const [productionError, setProductionError] = useState<string | null>(null)
  const [productionStats, setProductionStats] = useState({
    total: 0,
    passed: 0,
    failed: 0,
    llmEvaluated: 0,
    avgSoftScore: null as number | null,
  })

  // 归因标注和导出状态
  const [rootCauseModal, setRootCauseModal] = useState<{ open: boolean; itemId: number | null }>({ open: false, itemId: null })
  const [rootCauseForm, setRootCauseForm] = useState({
    category: '' as 'prompt_issue' | 'code_bug' | 'rule_too_strict' | 'edge_case' | '',
    note: '',
    fixed_in_version: '',
  })
  const [exportModal, setExportModal] = useState<{ open: boolean; itemId: number | null }>({ open: false, itemId: null })
  const [exportForm, setExportForm] = useState({
    description: '',
    expected_violations: [] as string[],
  })

  // 失败模式分析状态
  const [failureAnalysis, setFailureAnalysis] = useState<FailureAnalysis | null>(null)
  const [failureAnalysisLoading, setFailureAnalysisLoading] = useState(false)
  const [failureAnalysisError, setFailureAnalysisError] = useState<string | null>(null)

  const limit = 20

  // ── 加载评测结果列表 ───
  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await adminApi.evalResults({
        offset,
        limit,
        dataset_id: filterDatasetId || undefined,
        eval_type: filterEvalType || undefined,
      })
      // 前端按数据来源二次过滤
      let filtered = data?.items || []
      if (filterSource === 'lab') {
        filtered = filtered.filter(i => LAB_TYPES.has(i.eval_type || 'report_quality'))
      } else if (filterSource === 'production') {
        filtered = filtered.filter(i => i.eval_type === 'production_monitor')
      }
      setItems(filtered)
      setTotal(filtered.length)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [offset, filterDatasetId, filterEvalType, filterSource])

  // ── 加载版本列表 & 趋势数据 ───
  const loadVersions = useCallback(async () => {
    try {
      const { data } = await adminApi.evalResults({ offset: 0, limit: 100 })
      const items = data?.items || []
      const vList = items.map((item: EvalResultItem) => ({
        id: item.id,
        name: `v${item.id}`,
        created_at: item.created_at,
        eval_type: item.eval_type,
      }))
      setVersions(vList)
      setAllItems(items)

      if (vList.length > 0 && selectedVersion === null) {
        setSelectedVersion(vList[0].id)
      }

      const recent = items.slice(0, 10).reverse()
      setTrendMatchRate(recent.map(r => ({
        version_id: r.id,
        version_name: `v${r.id}`,
        value: parseFloat(((r.match_rate || 0) * 100).toFixed(1)),
        created_at: r.created_at,
      })))
      setTrendPassRate(recent.map(r => ({
        version_id: r.id,
        version_name: `v${r.id}`,
        value: parseFloat(((r.pass_rate || 0) * 100).toFixed(1)),
        created_at: r.created_at,
      })))
      setTrendFormatRate(recent.map(r => ({
        version_id: r.id,
        version_name: `v${r.id}`,
        value: r.format_pass_rate != null ? parseFloat((r.format_pass_rate * 100).toFixed(1)) : 0,
        created_at: r.created_at,
      })))
      setTrendTaskCompletion(recent.map(r => ({
        version_id: r.id,
        version_name: `v${r.id}`,
        value: r.task_completion_rate?.overall != null ? parseFloat((r.task_completion_rate.overall * 100).toFixed(1)) : 0,
        created_at: r.created_at,
      })))
    } catch (err) {
      // 静默失败
    }
  }, [selectedVersion])

  // ─── 加载选中版本的详情 ───
  const loadVersionDetail = useCallback(async (versionId: number) => {
    try {
      const { data } = await adminApi.evalResultDetail(versionId)
      setSelectedResult(data)
    } catch (err) {
      setSelectedResult(null)
    }
  }, [])

  // ─── 加载评测集 ───
  const loadDataset = useCallback(async () => {
    setDatasetLoading(true)
    setDatasetError(null)
    try {
      const [datasetRes, latestRes] = await Promise.all([
        adminApi.evalDataset(),
        adminApi.evalResults({ offset: 0, limit: 1 }),
      ])
      setDatasetItems(datasetRes.data?.items || [])
      setDatasetTotal(datasetRes.data?.total || 0)
      const latestItems = latestRes.data?.items || []
      if (latestItems.length > 0) {
        const detailRes = await adminApi.evalResultDetail(latestItems[0].id)
        setLatestEvalResult(detailRes.data)
      }
    } catch (err: any) {
      setDatasetError(err?.response?.data?.detail || '加载评测集失败')
    } finally {
      setDatasetLoading(false)
    }
  }, [])

  // ─── 加载概览数据 ──
  const loadOverview = useCallback(async () => {
    setOverviewError(null)
    try {
      const { data } = await adminApi.evalResults({ offset: 0, limit: 100 })
      const items = data?.items || []
      if (items.length === 0) {
        setOverviewError('暂无评测数据')
        return
      }

      // 最新版本详情
      const latestId = items[0].id
      const latestDetail = await adminApi.evalResultDetail(latestId)
      setLatestResult(latestDetail.data)

      // 评测类型分布
      const typeCount: Record<string, number> = {}
      items.forEach((item: any) => {
        const type = item.eval_type || 'report_quality'
        typeCount[type] = (typeCount[type] || 0) + 1
      })
      const distribution = Object.entries(typeCount).map(([type, count]) => ({
        name: EVAL_TYPE_MAP[type as keyof typeof EVAL_TYPE_MAP]?.label || type,
        value: count,
        color: EVAL_TYPE_MAP[type as keyof typeof EVAL_TYPE_MAP]?.color || '#6b7280',
      }))
      setTypeDistribution(distribution)
    } catch (err: any) {
      setOverviewError(err?.response?.data?.detail || '加载数据失败')
    }
  }, [])

  // ─── 加载生产监控数据 ───
  const loadProduction = useCallback(async () => {
    setProductionLoading(true)
    setProductionError(null)
    try {
      const { data } = await adminApi.evalResults({ offset: 0, limit: 100, eval_type: 'production_monitor' })
      const items = data?.items || []
      // 加载每条的详情（包含 LLM 评分）
      const detailPromises = items.map(item => adminApi.evalResultDetail(item.id).catch(() => null))
      const detailResults = await Promise.all(detailPromises)

      const enriched = items.map((item, idx) => {
        const detail = detailResults[idx]?.data as any
        const monitorDetail: any = detail?.detail?.[0] || {}
        const evalResult: any = monitorDetail.eval_result || {}
        return {
          ...item,
          trigger_reason: monitorDetail.trigger_reason || '-',
          is_first_report: monitorDetail.is_first_report || false,
          generation_time: monitorDetail.generation_time || 0,
          word_count: monitorDetail.word_count || 0,
          block_count: monitorDetail.block_count || 0,
          prompt_version: monitorDetail.prompt_version || '',
          question_preview: monitorDetail.question_preview || '',
          response_preview: monitorDetail.response_preview || '',
          eval_passed: evalResult.passed,
          avg_soft_score: evalResult.avg_soft_score ?? evalResult.llm_soft_score,
          hard_violations: evalResult.hard_violations ?? evalResult.l3_quality?.total_violations ?? 0,
          skip_reason: evalResult.skip_reason || '',
          eval_error: evalResult.error || '',
          // L2 格式完成
          l2_format: evalResult.l2_format || monitorDetail.l2_format || null,
          // L3 质量完成
          l3_quality: evalResult.l3_quality || null,
          // 违规明细（type/detail/location/reason）
          eval_violations: evalResult.violations || evalResult.l2_format?.violations || [],
          // 完整报告 JSON（供查看全貌与违规定位）
          report: monitorDetail.report || null,
          // 分层人工复核结果
          layer_reviews: monitorDetail.layer_reviews || null,
          // LLM 软性评分详情
          llm_soft_details: evalResult.llm_soft_details || null,
          fabrication: evalResult.fabrication || null,
          // 归因信息
          root_cause: monitorDetail.root_cause || null,
        }
      })
      setProductionItems(enriched)

      // 计算统计
      let totalSoft = 0
      let softCount = 0
      let llmCount = 0
      let passCount = 0
      let failCount = 0
      enriched.forEach((item: any) => {
        if (item.eval_passed !== undefined && item.eval_passed !== null) {
          llmCount++
          if (item.eval_passed) passCount++
          else failCount++
        }
        if (item.avg_soft_score != null) {
          totalSoft += item.avg_soft_score
          softCount++
        }
      })
      setProductionStats({
        total: enriched.length,
        passed: passCount,
        failed: failCount,
        llmEvaluated: llmCount,
        avgSoftScore: softCount > 0 ? parseFloat((totalSoft / softCount).toFixed(2)) : null,
      })
    } catch (err: any) {
      setProductionError(err?.response?.data?.detail || '加载生产监控数据失败')
    } finally {
      setProductionLoading(false)
    }
  }, [])

  // 切换 Tab 时加载对应数据
  useEffect(() => {
    if (activeTab === 'results') {
      load()
    } else if (activeTab === 'production') {
      loadProduction()
    } else if (activeTab === 'dataset') {
      loadDataset()
    } else {
      loadOverview()
    }
  }, [activeTab, load, loadProduction, loadDataset, loadOverview])

  // 初始加载版本列表
  useEffect(() => {
    loadVersions()
  }, [loadVersions])

  // 选中版本变化时加载详情
  useEffect(() => {
    if (selectedVersion !== null) {
      loadVersionDetail(selectedVersion)
    }
  }, [selectedVersion, loadVersionDetail])

  // 计算 delta
  const getDelta = (currentVal: number, trend: TrendPoint[]) => {
    if (trend.length < 2) return undefined
    const prevVal = trend[trend.length - 2]?.value ?? 0
    const diff = currentVal - prevVal
    if (Math.abs(diff) < 0.05) return { value: 0, type: 'unchanged' as const }
    return {
      value: Math.abs(diff),
      type: (diff > 0 ? 'increase' : 'decrease') as 'increase' | 'decrease',
    }
  }

  const handleVersionSelect = (versionId: number) => {
    setSelectedVersion(versionId)
  }

  const handleSelect = (id: number) => {
    setSelectedIds(prev => {
      if (prev.includes(id)) return prev.filter(x => x !== id)
      return [...prev, id].slice(-2)
    })
  }

  const handleCompare = () => {
    if (selectedIds.length === 2) {
      navigate(`/admin/eval-compare?baseline=${selectedIds[0]}&current=${selectedIds[1]}`)
    }
  }

  // 处理归因标注
  const handleRootCauseSubmit = async () => {
    if (!rootCauseModal.itemId || !rootCauseForm.category) return
    
    try {
      await adminApi.updateRootCause(rootCauseModal.itemId, {
        category: rootCauseForm.category as any,
        note: rootCauseForm.note,
        fixed_in_version: rootCauseForm.fixed_in_version,
      })
      
      // 更新本地数据
      setProductionItems(items => 
        items.map(item => {
          if (item.id === rootCauseModal.itemId) {
            return {
              ...item,
              root_cause: {
                category: rootCauseForm.category,
                note: rootCauseForm.note,
                fixed_in_version: rootCauseForm.fixed_in_version,
              }
            }
          }
          return item
        })
      )
      
      setRootCauseModal({ open: false, itemId: null })
      setRootCauseForm({ category: '', note: '', fixed_in_version: '' })
      alert('归因标注已保存')
    } catch (err: any) {
      alert('保存失败：' + (err?.response?.data?.detail || err.message))
    }
  }

  // 处理导出 badcase
  const handleExportBadcase = async () => {
    if (!exportModal.itemId) return

    try {
      const result = await adminApi.exportBadcase({
        eval_result_id: exportModal.itemId,
        description: exportForm.description,
        expected_violations: exportForm.expected_violations,
      })

      alert(result.data?.message || '导出成功')
      setExportModal({ open: false, itemId: null })
      setExportForm({ description: '', expected_violations: [] })
    } catch (err: any) {
      alert('导出失败：' + (err?.response?.data?.detail || err.message))
    }
  }

  // 加载失败模式分析
  const loadFailureAnalysis = async () => {
    setFailureAnalysisLoading(true)
    setFailureAnalysisError(null)
    try {
      const { data } = await adminApi.getFailureAnalysis(7, 2)
      setFailureAnalysis(data)
    } catch (err: any) {
      setFailureAnalysisError(err?.response?.data?.detail || '加载失败')
    } finally {
      setFailureAnalysisLoading(false)
    }
  }

  // 分层人工复核标注
  const handleLayerReview = async (itemId: number, layer: 'l1' | 'l2' | 'l3' | 'llm', verdict: 'agree' | 'disagree') => {
    let note = ''
    if (verdict === 'disagree') {
      note = window.prompt('不认同的原因（会作为调整检查规则的证据）：') || ''
      if (!note) return
    }
    try {
      await adminApi.updateLayerReview(itemId, { layer, verdict, note })
      alert('分层复核已保存')
      loadProduction()
    } catch (err: any) {
      alert('保存失败：' + (err?.response?.data?.detail || err.message))
    }
  }

  // 层级复核按钮与已有标注展示
  const renderLayerReview = (itemId: number, layer: 'l1' | 'l2' | 'l3' | 'llm', review: any) => (
    <span className="ml-auto flex items-center gap-1">
      {review && (
        <span className={`text-xs px-1.5 py-0.5 rounded ${review.verdict === 'agree' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          人工：{review.verdict === 'agree' ? '认同' : '不认同'}{review.note ? `（${review.note}）` : ''}
        </span>
      )}
      <button
        onClick={() => handleLayerReview(itemId, layer, 'agree')}
        className="text-xs px-1.5 py-0.5 rounded border border-green-200 text-green-700 hover:bg-green-50"
      >
        认同
      </button>
      <button
        onClick={() => handleLayerReview(itemId, layer, 'disagree')}
        className="text-xs px-1.5 py-0.5 rounded border border-red-200 text-red-700 hover:bg-red-50"
      >
        不认同
      </button>
    </span>
  )

  // 失败模式分析面板
  const violationTypeMap: Record<string, string> = {
    structure: '结构违规',
    narrative: '叙事违规',
    chart_usage: '命盘使用违规',
    low_soft_score: '软性评分偏低',
    fabrication: '编造信息',
  }
  const rootCauseMap: Record<string, string> = {
    prompt_issue: 'Prompt 问题',
    code_bug: '代码 Bug',
    rule_too_strict: '规则过严',
    edge_case: '边界情况',
  }

  const totalPages = Math.ceil(total / limit)

  // 当前选中版本的指标值
  const currentMatchRate = selectedResult ? parseFloat(((selectedResult.match_rate || 0) * 100).toFixed(1)) : 0
  const currentPassRate = selectedResult ? parseFloat(((selectedResult.pass_rate || 0) * 100).toFixed(1)) : 0
  const currentFormatRate = selectedResult?.format_pass_rate != null
    ? parseFloat((selectedResult.format_pass_rate * 100).toFixed(1))
    : 0
  const currentTaskCompletion = selectedResult?.task_completion_rate?.overall != null
    ? parseFloat((selectedResult.task_completion_rate.overall * 100).toFixed(1))
    : 0

  // 概览 Tab 指标值（已移至 EvalMethodology 组件）

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">评测中心</h1>

        {/* Tab 切换 */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {([
              { key: 'overview', label: '评测概览' },
              { key: 'results', label: '评测结果' },
              { key: 'production', label: '生产监控' },
              { key: 'dataset', label: '评测集内容' },
            ] as const).map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* ═══════ 评测概览 Tab ═══════ */}
        {activeTab === 'overview' && (
          <>
            {overviewError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div className="text-sm text-red-800">{overviewError}</div>
              </div>
            )}

            {/* 评测方法论组件 */}
            <EvalMethodology
              typeDistribution={typeDistribution}
              latestResult={latestResult}
              versions={versions}
              allItems={allItems}
            />
          </>
        )}

        {/* ═══════ 评测结果 Tab ═══════ */}
        {activeTab === 'results' && (
          <>
            {/* 版本选择器 + 指标说明 */}
            <div className="bg-white rounded-lg shadow p-4 mb-4">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <VersionSelector
                  versions={versions}
                  selectedVersion={selectedVersion || (versions[0]?.id ?? 0)}
                  onSelect={handleVersionSelect}
                />
                <div className="text-xs text-gray-500">
                  <strong>检测准确率</strong>=预期与实际匹配的比例 |
                  <strong>通过率</strong>=实际通过占比 |
                  <strong>L2格式完成率</strong>=JSON符合Schema比例
                </div>
              </div>
            </div>

            {/* 指标卡片：总指标 → L1-L4 分层 */}
            <div className="mb-4">
              {/* 总指标 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                <MetricCard
                  title="检测准确率（总）"
                  value={currentMatchRate}
                  unit="%"
                  trend={trendMatchRate.map(t => ({ version: t.version_name, value: t.value }))}
                  delta={getDelta(currentMatchRate, trendMatchRate)}
                  color="#3b82f6"
                  description="预期结果与实际结果匹配的比例"
                />
                <MetricCard
                  title="通过率（总）"
                  value={currentPassRate}
                  unit="%"
                  trend={trendPassRate.map(t => ({ version: t.version_name, value: t.value }))}
                  delta={getDelta(currentPassRate, trendPassRate)}
                  color="#8b5cf6"
                  description="通过硬性检查的报告比例"
                />
              </div>
              {/* L1-L4 分层指标 */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  title="L1 技术完成"
                  value={selectedResult?.task_completion_rate?.l1_technical != null
                    ? parseFloat((selectedResult.task_completion_rate.l1_technical * 100).toFixed(1))
                    : 0}
                  unit="%"
                  color="#10b981"
                  description="JSON解析 + Pydantic校验通过"
                />
                <MetricCard
                  title="L2 格式完成"
                  value={currentFormatRate}
                  unit="%"
                  trend={trendFormatRate.map(t => ({ version: t.version_name, value: t.value }))}
                  delta={getDelta(currentFormatRate, trendFormatRate)}
                  color="#06b6d4"
                  description="结构检查通过（子问题/block/narrative）"
                />
                <MetricCard
                  title="L3 质量完成"
                  value={selectedResult?.task_completion_rate?.l3_quality != null
                    ? parseFloat((selectedResult.task_completion_rate.l3_quality * 100).toFixed(1))
                    : 0}
                  color="#f59e0b"
                  description="叙事检查 + 命盘使用检查通过"
                />
                <MetricCard
                  title="L4 综合完成"
                  value={currentTaskCompletion}
                  unit="%"
                  trend={trendTaskCompletion.map(t => ({ version: t.version_name, value: t.value }))}
                  delta={getDelta(currentTaskCompletion, trendTaskCompletion)}
                  color="#8b5cf6"
                  description="L1×L2×L3 全部通过"
                />
              </div>
            </div>

            {/* 筛选区 */}
            <div className="bg-white rounded-lg shadow p-4 mb-4">
              <div className="flex gap-4 flex-wrap items-end">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">数据来源</label>
                  <select
                    value={filterSource}
                    onChange={e => { setFilterSource(e.target.value); setOffset(0) }}
                    className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                  >
                    <option value="">全部</option>
                    <option value="lab">实验室</option>
                    <option value="production">生产</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">评测类型</label>
                  <select
                    value={filterEvalType}
                    onChange={e => { setFilterEvalType(e.target.value); setOffset(0) }}
                    className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                  >
                    <option value="">全部</option>
                    {Object.entries(EVAL_TYPE_MAP).map(([key, val]) => (
                      <option key={key} value={key}>{val.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">评测集ID</label>
                  <input
                    type="text"
                    value={filterDatasetId}
                    onChange={e => { setFilterDatasetId(e.target.value); setOffset(0) }}
                    placeholder="输入评测集ID"
                    className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                  />
                </div>
              </div>
            </div>

            {/* 对比操作提示 */}
            {selectedIds.length > 0 && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-blue-900">
                    已选择 {selectedIds.length} 个评测结果
                    {selectedIds.length === 2 && ' - 可以进行对比'}
                  </span>
                  {selectedIds.length === 2 && (
                    <button
                      onClick={handleCompare}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                    >
                      对比选中版本
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* 表格 */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              {loading && <div className="p-8 text-center text-gray-500">加载中...</div>}
              {error && <div className="p-8 text-center text-red-500">{error}</div>}
              {!loading && !error && (
                <>
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">选择</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">评测类型</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">数据来源</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">评测集ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">总数</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">通过/失败</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">检测准确率</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">通过率</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L1技术</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L2格式</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L3质量</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">创建时间</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {items.map(item => {
                        const type = item.eval_type || 'report_quality'
                        const typeInfo = EVAL_TYPE_MAP[type]
                        const source = getSourceLabel(type)
                        return (
                          <tr
                            key={item.id}
                            className={`hover:bg-gray-50 ${selectedVersion === item.id ? 'bg-blue-50' : ''}`}
                          >
                            <td className="px-4 py-3">
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(item.id)}
                                onChange={() => handleSelect(item.id)}
                                disabled={selectedIds.length >= 2 && !selectedIds.includes(item.id)}
                                className="rounded"
                              />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">v{item.id}</td>
                            <td className="px-4 py-3 text-sm">
                              <span
                                className="text-xs px-2 py-0.5 rounded"
                                style={{
                                  backgroundColor: `${typeInfo?.color}15`,
                                  color: typeInfo?.color,
                                }}
                              >
                                {typeInfo?.label || type}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span
                                className="text-xs px-2 py-0.5 rounded"
                                style={{
                                  backgroundColor: `${source.color}15`,
                                  color: source.color,
                                }}
                              >
                                {source.label}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">{item.dataset_id}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{item.total}</td>
                            <td className="px-4 py-3 text-sm">
                              <span className="text-green-600">{item.passed}</span>
                              {' / '}
                              <span className="text-red-600">{item.failed}</span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span className={item.match_rate >= 0.8 ? 'text-green-600 font-medium' : item.match_rate >= 0.6 ? 'text-yellow-600 font-medium' : 'text-red-600 font-medium'}>
                                {((item.match_rate || 0) * 100).toFixed(1)}%
                              </span>
                              <span className="text-xs text-gray-500 ml-1">
                                ({item.match_count}/{item.total})
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              <span className={item.pass_rate >= 0.8 ? 'text-green-600' : item.pass_rate >= 0.6 ? 'text-yellow-600' : 'text-red-600'}>
                                {((item.pass_rate || 0) * 100).toFixed(1)}%
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {item.format_pass_rate != null ? (
                                <span className={item.format_pass_rate >= 0.9 ? 'text-green-600' : item.format_pass_rate >= 0.7 ? 'text-yellow-600' : 'text-red-600'}>
                                  {(item.format_pass_rate * 100).toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {item.task_completion_rate?.l1_technical != null ? (
                                <span className={item.task_completion_rate.l1_technical >= 0.9 ? 'text-green-600' : item.task_completion_rate.l1_technical >= 0.7 ? 'text-yellow-600' : 'text-red-600'}>
                                  {(item.task_completion_rate.l1_technical * 100).toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {item.task_completion_rate?.l3_quality != null ? (
                                <span className={item.task_completion_rate.l3_quality >= 0.9 ? 'text-green-600' : item.task_completion_rate.l3_quality >= 0.7 ? 'text-yellow-600' : 'text-red-600'}>
                                  {(item.task_completion_rate.l3_quality * 100).toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-500">{formatTime(item.created_at)}</td>
                            <td className="px-4 py-3 text-sm">
                              <button
                                onClick={() => navigate(`/admin/eval-detail/${item.id}`)}
                                className="text-blue-600 hover:text-blue-800 text-sm"
                              >
                                详情
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>

                  {/* 分页 */}
                  {total > limit && (
                    <div className="px-4 py-3 bg-white border-t border-gray-200 flex items-center justify-between">
                      <div className="text-sm text-gray-700">
                        共 <span className="font-medium">{total}</span> 条记录
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setOffset(Math.max(0, offset - limit))}
                          disabled={offset === 0}
                          className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50"
                        >
                          上一页
                        </button>
                        <span className="px-3 py-1 text-sm text-gray-700">
                          {Math.floor(offset / limit) + 1} / {totalPages}
                        </span>
                        <button
                          onClick={() => setOffset(Math.min(total - limit, offset + limit))}
                          disabled={offset + limit >= total}
                          className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50"
                        >
                          下一页
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {/* ═══════ 生产监控 Tab ═══════ */}
        {activeTab === 'production' && (
          <>
            {/* 统计卡片 */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-2xl font-bold text-gray-900">{productionStats.total}</div>
                <div className="text-sm text-gray-500 mt-1">总监控数</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-2xl font-bold text-purple-600">{productionStats.llmEvaluated}</div>
                <div className="text-sm text-gray-500 mt-1">LLM 已评测</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{productionStats.passed}</div>
                <div className="text-sm text-gray-500 mt-1">通过</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-2xl font-bold text-red-600">{productionStats.failed}</div>
                <div className="text-sm text-gray-500 mt-1">未通过</div>
              </div>
              <div className="bg-white rounded-lg shadow p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {productionStats.avgSoftScore != null ? productionStats.avgSoftScore.toFixed(1) : '-'}
                </div>
                <div className="text-sm text-gray-500 mt-1">平均软性评分</div>
              </div>
            </div>

            {/* 失败模式分析 */}
            <div className="bg-white rounded-lg shadow mb-4">
              <div className="flex items-center justify-between p-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">失败模式分析</h3>
                  <p className="text-xs text-gray-500 mt-0.5">统计最近 7 天高频违规模式、归因分布与改进建议</p>
                </div>
                <button
                  onClick={() => {
                    if (failureAnalysis) {
                      setFailureAnalysis(null)
                    } else {
                      loadFailureAnalysis()
                    }
                  }}
                  className="px-3 py-1.5 text-sm rounded-md border border-purple-200 text-purple-700 hover:bg-purple-50 whitespace-nowrap"
                >
                  {failureAnalysis ? '收起' : failureAnalysisLoading ? '分析中...' : '运行分析'}
                </button>
              </div>
              {failureAnalysisLoading && <div className="px-4 pb-4 text-sm text-gray-500">正在分析最近 7 天数据...</div>}
              {failureAnalysisError && <div className="px-4 pb-4 text-sm text-red-500">{failureAnalysisError}</div>}
              {failureAnalysis && !failureAnalysisLoading && (
                <div className="px-4 pb-4 border-t border-gray-100 pt-4 space-y-4">
                  {/* 基础统计 */}
                  <div className="flex flex-wrap gap-4 text-sm">
                    <span className="text-gray-600">总报告数: <b className="text-gray-900">{failureAnalysis.total_reports}</b></span>
                    <span className="text-gray-600">LLM 评测: <b className="text-gray-900">{failureAnalysis.llm_evaluated}</b></span>
                    <span className="text-green-600">通过: <b>{failureAnalysis.passed}</b></span>
                    <span className="text-red-600">未通过: <b>{failureAnalysis.failed}</b></span>
                    <span className="text-gray-600">通过率: <b className="text-gray-900">{failureAnalysis.pass_rate}%</b></span>
                  </div>

                  {/* 高频违规模式 */}
                  {failureAnalysis.high_frequency_patterns.length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-2">高频违规模式（≥2 次）</h4>
                      <div className="space-y-2">
                        {failureAnalysis.high_frequency_patterns.map((p: any) => (
                          <div key={p.type} className="bg-red-50 rounded-md p-3">
                            <div className="text-sm">
                              <span className="font-medium text-red-700">{violationTypeMap[p.type] || p.type}</span>
                              <span className="text-gray-600 ml-2">出现 {p.count} 次（{p.percentage}%）</span>
                            </div>
                            {p.examples?.length > 0 && (
                              <div className="text-xs text-gray-500 mt-1">
                                示例: {p.examples.slice(0, 3).map((e: any) => `#${e.id}`).join('、')}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 归因分布 */}
                  {Object.keys(failureAnalysis.root_cause_distribution).length > 0 && (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-2">问题归因分布</h4>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(failureAnalysis.root_cause_distribution).map(([cat, count]) => (
                          <span key={cat} className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700">
                            {rootCauseMap[cat] || cat}: {count as number}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 改进建议 */}
                  {failureAnalysis.improvement_suggestions.length > 0 ? (
                    <div>
                      <h4 className="text-xs font-semibold text-gray-700 mb-2">改进建议</h4>
                      <div className="space-y-2">
                        {failureAnalysis.improvement_suggestions.map((s: any, i: number) => (
                          <div
                            key={i}
                            className={`rounded-md p-3 text-sm ${s.priority === 'high' ? 'bg-orange-50' : 'bg-gray-50'}`}
                          >
                            <div className="font-medium">
                              {s.priority === 'high' ? '🔴' : '🟡'} [{s.category}] {s.issue}
                            </div>
                            <div className="text-gray-600 mt-1">建议: {s.suggestion}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-500">暂无改进建议（数据量不足或无高频模式）</div>
                  )}
                </div>
              )}
            </div>

            {/* 监控列表 */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
              {productionLoading && <div className="p-8 text-center text-gray-500">加载中...</div>}
              {productionError && <div className="p-8 text-center text-red-500">{productionError}</div>}
              {!productionLoading && !productionError && productionItems.length === 0 && (
                <div className="p-8 text-center text-gray-500">暂无生产监控数据</div>
              )}
              {!productionLoading && !productionError && productionItems.length > 0 && (
                <div className="divide-y divide-gray-200">
                  {productionItems.map((item: any) => {
                    const triggerMap: Record<string, { label: string; color: string }> = {
                      first_report: { label: '首次报告', color: '#ef4444' },
                      sensitive_topic: { label: '敏感话题', color: '#f59e0b' },
                      negative_emotion: { label: '负面情绪', color: '#f59e0b' },
                      rule_violation: { label: '规则违规', color: '#f97316' },
                      light_metric: { label: '指标异常', color: '#eab308' },
                      random_sample: { label: '随机采样', color: '#6b7280' },
                      no_trigger: { label: '未触发LLM', color: '#9ca3af' },
                    }
                    const triggerInfo = triggerMap[item.trigger_reason] || { label: item.trigger_reason, color: '#6b7280' }
                    const hasEval = item.eval_passed !== undefined && item.eval_passed !== null
                    const isPassed = item.eval_passed === true

                    // 解析违规 location，标记报告中违规的段落
                    const violatedBlocks = new Map<string, any[]>()   // key: "子话题-块"
                    const violatedSubtopics = new Set<string>()       // key: 子话题索引
                    const violatedSections = new Set<string>()        // opening / summary
                    ;(item.eval_violations || []).forEach((v: any) => {
                      const loc: string = v.location || ''
                      const blockMatch = loc.match(/subtopics\[(\d+)\]\.blocks\[(\d+)\]/)
                      if (blockMatch) {
                        const key = `${blockMatch[1]}-${blockMatch[2]}`
                        violatedBlocks.set(key, [...(violatedBlocks.get(key) || []), v])
                        return
                      }
                      const subMatch = loc.match(/^subtopics\[(\d+)\]/)
                      if (subMatch) {
                        violatedSubtopics.add(subMatch[1])
                        return
                      }
                      if (loc.startsWith('opening')) violatedSections.add('opening')
                      else if (loc.startsWith('summary')) violatedSections.add('summary')
                    })

                    // LLM编造内容 → 定位到报告段落（文本包含匹配，启发式）
                    const fabBlocks = new Map<string, string[]>()
                    const fabSections = new Set<string>()
                    ;(item.fabrication?.['编造内容'] || []).forEach((fab: string) => {
                      if (!fab || !item.report) return
                      const probe = fab.length > 25 ? fab.slice(0, 25) : fab
                      const openingText = (item.report.opening?.lead || '') + (item.report.opening?.verdict || '')
                      if (openingText.includes(probe)) { fabSections.add('opening'); return }
                      let matched = false
                      ;(item.report.summary?.items || []).forEach((it: any) => {
                        if ((it.text || '').includes(probe)) { fabSections.add('summary'); matched = true }
                      })
                      if (matched) return
                      ;(item.report.subtopics || []).forEach((sub: any, si: number) => {
                        ;(sub.blocks || []).forEach((blk: any, bi: number) => {
                          if ((blk.narrative || '').includes(probe)) {
                            const key = `${si}-${bi}`
                            fabBlocks.set(key, [...(fabBlocks.get(key) || []), fab])
                            matched = true
                          }
                        })
                      })
                    })

                    return (
                      <div key={item.id} className="p-4 hover:bg-gray-50">
                        {/* 头部：ID + 触发原因 + 评测结果 */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-mono text-gray-400">#{item.id}</span>
                            <span
                              className="text-xs px-2 py-0.5 rounded"
                              style={{ backgroundColor: `${triggerInfo.color}15`, color: triggerInfo.color }}
                            >
                              {triggerInfo.label}
                            </span>
                            {item.is_first_report && (
                              <span className="text-xs px-2 py-0.5 rounded bg-blue-50 text-blue-700">首次报告</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {hasEval ? (
                              <span className={`text-xs px-2 py-1 rounded font-medium ${
                                isPassed ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                              }`}>
                                {isPassed ? '通过' : '未通过'}
                              </span>
                            ) : (
                              <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-500">
                                {item.skip_reason || '未评测'}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* 用户问题 */}
                        <div className="text-sm text-gray-700 mb-2 bg-blue-50 border border-blue-100 rounded px-3 py-2">
                          <span className="text-xs text-blue-500 font-medium">👤 用户问题：</span>
                          {item.question_preview || '（无问题预览）'}
                        </div>

                        {/* 系统回复 */}
                        {item.response_preview && (
                          <div className="text-sm text-gray-700 mb-2 bg-green-50 border border-green-100 rounded px-3 py-2">
                            <span className="text-xs text-green-600 font-medium">🤖 系统回复：</span>
                            {item.response_preview}
                          </div>
                        )}

                        {/* 指标行 */}
                        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                          <span>耗时 <strong className="text-gray-700">{item.generation_time}s</strong></span>
                          <span>字数 <strong className="text-gray-700">{item.word_count}</strong></span>
                          <span>Block <strong className="text-gray-700">{item.block_count}</strong></span>
                          {item.prompt_version && (
                            <span>Prompt <strong className="text-gray-700">{item.prompt_version}</strong></span>
                          )}
                          {/* L2 格式完成 */}
                          {item.l2_format && (
                            <span>
                              L2 格式{' '}
                              <strong className={item.l2_format.passed ? 'text-green-600' : 'text-red-600'}>
                                {item.l2_format.passed ? '✅' : '❌'}
                              </strong>
                              {item.l2_format.total_violations > 0 && (
                                <span className="text-red-500 ml-1">
                                  ({item.l2_format.structure_violations}结构/{item.l2_format.narrative_violations}叙事/{item.l2_format.chart_usage_violations}命盘)
                                </span>
                              )}
                            </span>
                          )}
                          {/* L3 质量完成 */}
                          {item.l3_quality && (
                            <span>
                              L3 质量{' '}
                              <strong className={item.l3_quality.passed ? 'text-green-600' : 'text-red-600'}>
                                {item.l3_quality.passed ? '✅' : '❌'}
                              </strong>
                              {item.l3_quality.total_violations > 0 && (
                                <span className="text-red-500 ml-1">
                                  ({item.l3_quality.blocked_by || '未知'})
                                </span>
                              )}
                            </span>
                          )}
                          {/* LLM 软性评分 */}
                          {hasEval && item.avg_soft_score != null && (
                            <span>LLM 评分 <strong className="text-blue-600">{item.avg_soft_score.toFixed(2)}</strong></span>
                          )}
                          <span className="ml-auto text-gray-400">{formatTime(item.created_at)}</span>
                        </div>

                        {/* 操作按钮 */}
                        <div className="mt-2 flex gap-2">
                          <button
                            onClick={() => {
                              setRootCauseModal({ open: true, itemId: item.id })
                              setRootCauseForm({
                                category: (item.root_cause?.category as any) || '',
                                note: item.root_cause?.note || '',
                                fixed_in_version: item.root_cause?.fixed_in_version || '',
                              })
                            }}
                            className="px-3 py-1 text-xs bg-orange-50 text-orange-700 rounded hover:bg-orange-100 border border-orange-200"
                          >
                            {item.root_cause?.category ? '修改归因' : '标注归因'}
                          </button>
                          {hasEval && !isPassed && (
                            <button
                              onClick={() => {
                                setExportModal({ open: true, itemId: item.id })
                                setExportForm({
                                  description: `生产监控-${item.trigger_reason}-${item.question_preview?.slice(0, 20) || ''}`,
                                  expected_violations: [],
                                })
                              }}
                              className="px-3 py-1 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100 border border-purple-200"
                            >
                              导出到评测集
                            </button>
                          )}
                          {item.root_cause?.category && (
                            <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                              已归因: {
                                item.root_cause.category === 'prompt_issue' ? 'Prompt问题' :
                                item.root_cause.category === 'code_bug' ? '代码Bug' :
                                item.root_cause.category === 'rule_too_strict' ? '规则过严' :
                                item.root_cause.category === 'edge_case' ? '边界情况' : item.root_cause.category
                              }
                            </span>
                          )}
                        </div>

                        {/* 展开详情按钮 */}
                        {hasEval && (
                          <details className="mt-2 text-xs">
                            <summary className="cursor-pointer text-blue-600 hover:text-blue-800">查看详情</summary>
                            <div className="mt-2 p-3 bg-gray-50 rounded text-xs space-y-2">
                              {/* L1 技术完成 */}
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-gray-700">L1 技术完成：</span>
                                <span className="text-green-600">✅ 通过</span>
                                <span className="text-gray-400">(JSON解析 + Pydantic校验)</span>
                                {renderLayerReview(item.id, 'l1', item.layer_reviews?.l1)}
                              </div>
                              {/* L2 格式完成 */}
                              {item.l2_format && (
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-medium text-gray-700">L2 格式完成：</span>
                                  <span className={item.l2_format.passed ? 'text-green-600' : 'text-red-600'}>
                                    {item.l2_format.passed ? '✅ 通过' : '❌ 未通过'}
                                  </span>
                                  {item.l2_format.total_violations > 0 && (
                                    <span className="text-gray-500">
                                      (结构违规:{item.l2_format.structure_violations} 叙事违规:{item.l2_format.narrative_violations} 命盘违规:{item.l2_format.chart_usage_violations})
                                    </span>
                                  )}
                                  {item.l2_format.blocked_by && (
                                    <span className="text-red-500">被拦截：{item.l2_format.blocked_by}</span>
                                  )}
                                  {renderLayerReview(item.id, 'l2', item.layer_reviews?.l2)}
                                </div>
                              )}
                              {/* L3 质量完成 */}
                              {item.l3_quality && (
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-gray-700">L3 质量完成：</span>
                                  <span className={item.l3_quality.passed ? 'text-green-600' : 'text-red-600'}>
                                    {item.l3_quality.passed ? '✅ 通过' : '❌ 未通过'}
                                  </span>
                                  {item.l3_quality.total_violations > 0 && (
                                    <span className="text-gray-500">
                                      (违规数:{item.l3_quality.total_violations})
                                    </span>
                                  )}
                                  {item.l3_quality.blocked_by && (
                                    <span className="text-red-500">被拦截：{item.l3_quality.blocked_by}</span>
                                  )}
                                  {renderLayerReview(item.id, 'l3', item.layer_reviews?.l3)}
                                </div>
                              )}
                              {/* 违规明细：定位具体内容与原因 */}
                              {item.eval_violations?.length > 0 && (
                                <div>
                                  <div className="font-medium text-gray-700 mb-1">违规明细（{item.eval_violations.length} 条）：</div>
                                  <div className="space-y-2">
                                    {item.eval_violations.map((v: any, i: number) => (
                                      <div key={i} className="bg-white border border-red-100 rounded p-2">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="text-red-600 font-medium">{v.type}</span>
                                          {v.location && <span className="text-gray-400">位置：{v.location}</span>}
                                        </div>
                                        {v.detail && <div className="text-gray-700 mt-1">问题：{v.detail}</div>}
                                        {v.reason && <div className="text-gray-500 mt-0.5">规则原因：{v.reason}</div>}
                                        {v.expected !== undefined && (
                                          <div className="text-gray-500 mt-0.5">
                                            期望：{typeof v.expected === 'object' ? JSON.stringify(v.expected) : String(v.expected)}
                                            {v.actual !== undefined
                                              ? `｜实际：${typeof v.actual === 'object' ? JSON.stringify(v.actual) : String(v.actual)}`
                                              : v['命盘已有'] !== undefined
                                                ? `｜命盘已有：${typeof v['命盘已有'] === 'object' ? JSON.stringify(v['命盘已有']) : String(v['命盘已有'])}`
                                                : ''}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {/* LLM 软性评分 */}
                              {item.avg_soft_score != null && (
                                <div className="flex items-center gap-2">
                                  <span className="font-medium text-gray-700">LLM 软性评分：</span>
                                  <span className="text-blue-600 font-bold">{item.avg_soft_score.toFixed(2)}</span>
                                  {item.llm_soft_details && typeof item.llm_soft_details === 'object' && (
                                    <span className="text-gray-500">
                                      (叙事:{item.llm_soft_details['叙事性'] || '-'} 通顺:{item.llm_soft_details['通顺性'] || '-'} 故事:{item.llm_soft_details['故事性'] || '-'} 加粗:{item.llm_soft_details['加粗合理性'] || '-'} 术语:{item.llm_soft_details['术语通俗化'] || '-'})
                                    </span>
                                  )}
                                  {renderLayerReview(item.id, 'llm', item.layer_reviews?.llm)}
                                </div>
                              )}
                              {/* 编造检测 */}
                              {item.fabrication && item.fabrication['编造'] !== undefined && (
                                <div>
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium text-gray-700">编造检测：</span>
                                    <span className={item.fabrication['编造'] ? 'text-red-600' : 'text-green-600'}>
                                      {item.fabrication['编造'] ? '⚠️ 发现编造' : '✅ 无编造'}
                                    </span>
                                    {item.fabrication['严重程度'] && (
                                      <span className={
                                        item.fabrication['严重程度'] === 'high' ? 'text-red-600' :
                                        item.fabrication['严重程度'] === 'medium' ? 'text-yellow-600' : 'text-gray-500'
                                      }>
                                        (严重程度:{item.fabrication['严重程度']})
                                      </span>
                                    )}
                                  </div>
                                  {item.fabrication['编造'] && (item.fabrication['编造内容'] || []).length > 0 && (
                                    <div className="ml-16 text-red-600">
                                      {item.fabrication['编造内容'].map((fab: string, k: number) => (
                                        <div key={k}>· {fab}</div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              )}
                              {/* 跳过原因 */}
                              {item.skip_reason && (
                                <div className="text-gray-500">跳过原因：{item.skip_reason}</div>
                              )}
                              {/* 错误信息 */}
                              {item.eval_error && (
                                <div className="text-red-600">错误：{item.eval_error}</div>
                              )}
                            </div>
                          </details>
                        )}

                        {/* 报告全貌（违规段落红色标注） */}
                        <details className="mt-1 text-xs">
                          <summary className="cursor-pointer text-blue-600 hover:text-blue-800">查看报告全貌（违规段落红色标注）</summary>
                          <div className="mt-2">
                            {!item.report ? (
                              <div className="p-3 bg-gray-50 rounded text-gray-400">该记录未存完整报告（旧数据），仅显示上方预览</div>
                            ) : (
                              <div className="space-y-2">
                                {/* 开头 */}
                                {item.report.opening && (
                                  <div className={`rounded p-2 border ${violatedSections.has('opening') || fabSections.has('opening') ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'}`}>
                                    <div className="text-gray-400 mb-1">【开头】</div>
                                    {item.report.opening.lead && <div className="text-sm text-gray-800">{item.report.opening.lead}</div>}
                                    {item.report.opening.verdict && <div className="text-sm text-gray-600 mt-1">【判断】{item.report.opening.verdict}</div>}
                                  </div>
                                )}
                                {/* 子话题 */}
                                {(item.report.subtopics || []).map((sub: any, si: number) => (
                                  <div key={si} className={`rounded p-2 border ${violatedSubtopics.has(String(si)) ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'}`}>
                                    <div className="text-gray-500 font-medium mb-1">【{sub.title || `子话题${si + 1}`}】</div>
                                    <div className="space-y-2">
                                      {(sub.blocks || []).map((blk: any, bi: number) => {
                                        const vs = violatedBlocks.get(`${si}-${bi}`) || []
                                        const fabs = fabBlocks.get(`${si}-${bi}`) || []
                                        return (
                                          <div key={bi} className={`rounded p-2 ${vs.length + fabs.length > 0 ? 'border border-red-500 bg-red-50' : 'bg-gray-50'}`}>
                                            <div className="text-sm font-medium text-gray-800">{blk.keyword}</div>
                                            <div className="text-sm text-gray-700 mt-0.5">{blk.narrative}</div>
                                            {vs.map((v: any, k: number) => (
                                              <div key={`v${k}`} className="text-red-600 mt-1">⚠ {v.type}：{v.detail}</div>
                                            ))}
                                            {fabs.map((fab: string, k: number) => (
                                              <div key={`f${k}`} className="text-red-600 mt-1">⚠ LLM编造检测：{fab}</div>
                                            ))}
                                          </div>
                                        )
                                      })}
                                    </div>
                                  </div>
                                ))}
                                {/* 总结 */}
                                {item.report.summary && (
                                  <div className={`rounded p-2 border ${violatedSections.has('summary') || fabSections.has('summary') ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'}`}>
                                    <div className="text-gray-400 mb-1">【总结】</div>
                                    {(item.report.summary.items || []).map((it: any, k: number) => (
                                      <div key={k} className="text-sm text-gray-700">· <b>{it.keyword}</b>：{it.text}</div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </details>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </>
        )}

        {/* ═══════ 评测集内容 Tab ═══════ */}
        {activeTab === 'dataset' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            {datasetLoading && <div className="p-8 text-center text-gray-500">加载中...</div>}
            {datasetError && <div className="p-8 text-center text-red-500">{datasetError}</div>}
            {!datasetLoading && !datasetError && (
              <>
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <div className="text-sm text-gray-700">
                    共 <span className="font-medium">{datasetTotal}</span> 个评测用例
                    {latestEvalResult && (
                      <span className="ml-4 text-gray-500">
                        最新评测：{formatTime(latestEvalResult.created_at)}
                      </span>
                    )}
                  </div>
                  {latestEvalResult && (
                    <div className="mt-2 flex items-center gap-6 text-sm">
                      <div>
                        <span className="text-gray-600">检测准确率：</span>
                        <span className={`font-medium ${
                          latestEvalResult.match_rate >= 0.8 ? 'text-green-600' :
                          latestEvalResult.match_rate >= 0.6 ? 'text-yellow-600' : 'text-red-600'
                        }`}>
                          {((latestEvalResult.match_rate || 0) * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs text-gray-500 ml-1">
                          ({latestEvalResult.match_count}/{latestEvalResult.total})
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">通过率：</span>
                        <span className="text-gray-700">
                          {((latestEvalResult.pass_rate || 0) * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs text-gray-500 ml-1">
                          ({latestEvalResult.passed}/{latestEvalResult.total})
                        </span>
                      </div>
                    </div>
                  )}
                  <div className="text-xs text-gray-500 mt-2">
                    检测逻辑：预期失败 + 实际失败 = 检测通过；预期通过 + 实际通过 = 检测通过
                  </div>
                </div>
                <div className="divide-y divide-gray-200">
                  {datasetItems.map((item, idx) => {
                    const caseResult = latestEvalResult?.detail?.find((c: any) => c.id === item.id)
                    const actualPass = caseResult?.passed
                    const match = caseResult?.match

                    let matchDescription = ''
                    if (match !== undefined) {
                      if (match) {
                        matchDescription = item.expected_pass && actualPass
                          ? '预期通过 + 实际通过 = 检测通过'
                          : '预期失败 + 实际失败 = 检测通过'
                      } else {
                        matchDescription = item.expected_pass && !actualPass
                          ? '预期通过 + 实际失败 = 检测失败'
                          : '预期失败 + 实际通过 = 检测失败'
                      }
                    }

                    return (
                      <div key={item.id || idx} className="p-4 hover:bg-gray-50">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded mr-2">
                              {item.id}
                            </span>
                            <span className="text-sm font-medium text-gray-900">{item.description}</span>
                          </div>
                          <div className="flex gap-2 items-center">
                            <span className={`text-xs px-2 py-1 rounded ${
                              item.expected_pass ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                            }`}>
                              预期：{item.expected_pass ? '通过' : '失败'}
                            </span>
                            {actualPass !== undefined && (
                              <span className={`text-xs px-2 py-1 rounded ${
                                actualPass ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                              }`}>
                                实际：{actualPass ? '通过' : '失败'}
                              </span>
                            )}
                            {match !== undefined && (
                              <span className={`text-xs px-2 py-1 rounded font-medium ${
                                match ? 'bg-green-100 text-green-800 border border-green-300' : 'bg-red-100 text-red-800 border border-red-300'
                              }`}>
                                {match ? '检测通过' : '检测失败'}
                              </span>
                            )}
                          </div>
                        </div>

                        {matchDescription && (
                          <div className={`text-xs mb-2 px-2 py-1 rounded ${
                            match ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                          }`}>
                            {matchDescription}
                          </div>
                        )}

                        <div className="text-sm text-gray-600 mb-2">
                          <strong>用户问题：</strong>{item.user_question}
                        </div>
                        {item.check_points && item.check_points.length > 0 && (
                          <div className="text-xs text-gray-500 mb-2">
                            <strong>检测内容：</strong>
                            {item.check_points.map((point: string, i: number) => (
                              <span key={i} className="inline-block bg-gray-100 px-2 py-0.5 rounded mr-1 mb-1">
                                {point}
                              </span>
                            ))}
                          </div>
                        )}
                        {caseResult?.violations && caseResult.violations.length > 0 && (
                          <div className="text-xs text-red-600 mt-2">
                            <strong>检测到的问题：</strong>
                            <ul className="list-disc list-inside mt-1">
                              {caseResult.violations.map((v: any, i: number) => (
                                <li key={i}>{v.type}: {v.detail}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* 归因标注模态框 */}
      {rootCauseModal.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">标注问题归因</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">问题类型</label>
                <select
                  value={rootCauseForm.category}
                  onChange={(e) => setRootCauseForm({ ...rootCauseForm, category: e.target.value as any })}
                  className="w-full px-3 py-2 border border-gray-300 rounded"
                >
                  <option value="">请选择</option>
                  <option value="prompt_issue">Prompt 问题</option>
                  <option value="code_bug">代码 Bug</option>
                  <option value="rule_too_strict">评测规则过严</option>
                  <option value="edge_case">边界情况</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">备注说明</label>
                <textarea
                  value={rootCauseForm.note}
                  onChange={(e) => setRootCauseForm({ ...rootCauseForm, note: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded"
                  rows={3}
                  placeholder="详细描述问题原因..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">修复版本</label>
                <input
                  type="text"
                  value={rootCauseForm.fixed_in_version}
                  onChange={(e) => setRootCauseForm({ ...rootCauseForm, fixed_in_version: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded"
                  placeholder="例如：v1.2.3"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setRootCauseModal({ open: false, itemId: null })}
                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleRootCauseSubmit}
                disabled={!rootCauseForm.category}
                className="flex-1 px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:bg-gray-300"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 导出 Badcase 模态框 */}
      {exportModal.open && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-bold mb-4">导出到评测集</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">用例描述</label>
                <input
                  type="text"
                  value={exportForm.description}
                  onChange={(e) => setExportForm({ ...exportForm, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded"
                  placeholder="描述这个 badcase 的场景"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">预期违规类型</label>
                <div className="space-y-2">
                  {['structure', 'narrative', 'chart_usage', 'terminology', 'fabrication'].map(type => (
                    <label key={type} className="flex items-center">
                      <input
                        type="checkbox"
                        checked={exportForm.expected_violations.includes(type)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setExportForm({
                              ...exportForm,
                              expected_violations: [...exportForm.expected_violations, type]
                            })
                          } else {
                            setExportForm({
                              ...exportForm,
                              expected_violations: exportForm.expected_violations.filter(v => v !== type)
                            })
                          }
                        }}
                        className="mr-2"
                      />
                      <span className="text-sm">
                        {type === 'structure' && '结构问题'}
                        {type === 'narrative' && '叙事问题'}
                        {type === 'chart_usage' && '命盘使用问题'}
                        {type === 'terminology' && '术语违规'}
                        {type === 'fabrication' && '编造信息'}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={() => setExportModal({ open: false, itemId: null })}
                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleExportBadcase}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700"
              >
                导出
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
