import { useState, useEffect, useCallback } from 'react'
import { adminApi, type FailureAnalysis } from '../api/admin'
import AdminNav from '../components/AdminNav'
import { genderToText, genderIcon } from '../utils/gender'

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function EvalDashboard() {
  // 生产监控数据
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
  const [productionPage, setProductionPage] = useState(0)
  const [productionPageSize] = useState(20)
  const [productionTotal, setProductionTotal] = useState(0)
  const [productionDateFrom, setProductionDateFrom] = useState('')
  const [productionDateTo, setProductionDateTo] = useState('')
  const [expandedDetail, setExpandedDetail] = useState<Record<number, { data?: any; loading?: boolean }>>({})
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

  // ─── 加载生产监控数据 ───
  // 按需加载单条详情（完整report/违规明细/LLM评分），展开查看详情时才调
  const loadDetail = useCallback(async (itemId: number) => {
    if (expandedDetail[itemId]?.data || expandedDetail[itemId]?.loading) return
    setExpandedDetail(prev => ({ ...prev, [itemId]: { loading: true } }))
    try {
      const { data } = await adminApi.evalResultDetail(itemId)
      const monitorDetail: any = data?.detail?.[0] || {}
      const evalResult: any = monitorDetail.eval_result || {}
      setExpandedDetail(prev => ({
        ...prev,
        [itemId]: {
          loading: false,
          data: {
            report: monitorDetail.report || null,
            eval_violations: evalResult.violations || evalResult.l2_format?.violations || [],
            llm_soft_details: evalResult.llm_soft_details || null,
            layer_reviews: monitorDetail.layer_reviews || null,
            response_preview: monitorDetail.response_preview || '',
          },
        },
      }))
    } catch {
      setExpandedDetail(prev => ({ ...prev, [itemId]: { loading: false } }))
    }
  }, [expandedDetail])

  const loadProduction = useCallback(async (page = productionPage, dateFrom = productionDateFrom, dateTo = productionDateTo) => {
    setProductionLoading(true)
    setProductionError(null)
    try {
      const { data } = await adminApi.evalResults({
        offset: page * productionPageSize,
        limit: productionPageSize,
        eval_type: 'production_monitor',
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      } as any)
      const items = data?.items || []
      // 直接用列表接口返回的 monitor_summary 概要，不再对每条发详情请求（去N+1，101请求→1请求）
      const enriched = items.map((item: any) => {
        const ms = item.monitor_summary || {}
        return {
          ...item,
          trigger_reason: ms.trigger_reason || '-',
          is_first_report: ms.is_first_report || false,
          generation_time: ms.generation_time || 0,
          word_count: ms.word_count || 0,
          block_count: ms.block_count || 0,
          prompt_version: ms.prompt_version || '',
          question_preview: ms.question_preview || '',
          response_preview: '',
          eval_passed: ms.eval_passed,
          avg_soft_score: ms.avg_soft_score,
          hard_violations: ms.hard_violations ?? 0,
          skip_reason: ms.skip_reason || '',
          eval_error: ms.eval_error || '',
          l2_format: ms.l2_format || null,
          l3_quality: ms.l3_quality || null,
          eval_violations: [],  // 按需加载
          report: null,  // 按需加载
          layer_reviews: null,
          llm_soft_details: null,
          fabrication: ms.fabrication || null,
          root_cause: ms.root_cause || null,
          user_id: ms.user_id,
          session_id: ms.session_id,
          bazi: ms.bazi || '',
          gender: ms.gender || '',
          birth_date: ms.birth_date || '',
          birth_time: ms.birth_time || '',
          birth_location: ms.birth_location || '',
        }
      })
      setProductionItems(enriched)
      setProductionTotal(data?.total || 0)
      setExpandedDetail({})  // 清空按需详情缓存
      // 统计基于当前页
      let totalSoft = 0, softCount = 0, llmCount = 0, passCount = 0, failCount = 0
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
        total: data?.total || enriched.length,
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
  }, [productionPage, productionPageSize, productionDateFrom, productionDateTo])

  // 切换 Tab 时加载对应数据
  // 初始加载生产监控数据
  useEffect(() => {
    loadProduction()
  }, [loadProduction])

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

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">生产监控</h1>

        {/* ═══════ 生产监控 ═══════ */}
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
              {/* 时间筛选 + 分页信息 */}
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-3 flex-wrap text-sm">
                <span className="text-gray-600">时间筛选：</span>
                <input type="date" value={productionDateFrom} onChange={e => setProductionDateFrom(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                <span className="text-gray-400">至</span>
                <input type="date" value={productionDateTo} onChange={e => setProductionDateTo(e.target.value)} className="border rounded px-2 py-1 text-xs" />
                <button onClick={() => { setProductionPage(0); loadProduction(0) }} className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700">查询</button>
                {(productionDateFrom || productionDateTo) && (
                  <button onClick={() => { setProductionDateFrom(''); setProductionDateTo(''); setProductionPage(0); loadProduction(0, '', '') }} className="px-2 py-1 text-gray-500 text-xs hover:text-gray-700">重置</button>
                )}
                <span className="ml-auto text-gray-500">共 {productionTotal} 条，第 {productionPage + 1}/{Math.max(1, Math.ceil(productionTotal / productionPageSize))} 页</span>
              </div>
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

                    // 按需加载的详情（完整report/违规明细，展开查看详情时才加载）
                    const ed = expandedDetail[item.id]?.data

                    // 解析违规 location，标记报告中违规的段落
                    const violatedBlocks = new Map<string, any[]>()   // key: "子话题-块"
                    const violatedSubtopics = new Set<string>()       // key: 子话题索引
                    const violatedSections = new Set<string>()        // opening / summary
                    ;(ed?.eval_violations || []).forEach((v: any) => {
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
                      if (!fab || !ed?.report) return
                      const probe = fab.length > 25 ? fab.slice(0, 25) : fab
                      const openingText = (ed.report.opening?.lead || '') + (ed.report.opening?.verdict || '')
                      if (openingText.includes(probe)) { fabSections.add('opening'); return }
                      let matched = false
                      ;(ed.report.summary?.items || []).forEach((it: any) => {
                        if ((it.text || '').includes(probe)) { fabSections.add('summary'); matched = true }
                      })
                      if (matched) return
                      ;(ed.report.subtopics || []).forEach((sub: any, si: number) => {
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

                        {/* 用户 & 命盘标识 */}
                        {(item.user_id || item.bazi) && (
                          <div className="text-xs text-gray-500 mb-2 flex flex-wrap items-center gap-3">
                            {item.user_id !== undefined && (
                              <span>👤 用户 <strong className="text-gray-700">#{item.user_id}</strong></span>
                            )}
                            {item.gender && (
                              <span>
                                {genderIcon(item.gender)}
                                <strong className="text-gray-700">{genderToText(item.gender)}</strong>
                              </span>
                            )}
                            {(item.birth_date || item.birth_time) && (
                              <span>
                                📅 <strong className="text-gray-700">
                                  {item.birth_date}{item.birth_time ? ` ${item.birth_time}` : ''}
                                </strong>
                              </span>
                            )}
                            {item.birth_location && (
                              <span>📍 <strong className="text-gray-700">{item.birth_location}</strong></span>
                            )}
                            {item.bazi && (
                              <span>
                                🀄 八字 <strong className="text-amber-700 font-mono tracking-wider">{item.bazi}</strong>
                              </span>
                            )}
                          </div>
                        )}

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
                          <details className="mt-2 text-xs" onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open) loadDetail(item.id) }}>
                            <summary className="cursor-pointer text-blue-600 hover:text-blue-800">查看详情</summary>
                            <div className="mt-2 p-3 bg-gray-50 rounded text-xs space-y-2">
                              {expandedDetail[item.id]?.loading && <div className="text-gray-500">加载详情中...</div>}
                              {/* L1 技术完成 */}
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-gray-700">L1 技术完成：</span>
                                <span className="text-green-600">✅ 通过</span>
                                <span className="text-gray-400">(JSON解析 + Pydantic校验)</span>
                                {renderLayerReview(item.id, 'l1', ed?.layer_reviews?.l1)}
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
                                  {renderLayerReview(item.id, 'l2', ed?.layer_reviews?.l2)}
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
                                  {renderLayerReview(item.id, 'l3', ed?.layer_reviews?.l3)}
                                </div>
                              )}
                              {/* 违规明细：定位具体内容与原因 */}
                              {ed?.eval_violations?.length > 0 && (
                                <div>
                                  <div className="font-medium text-gray-700 mb-1">违规明细（{ed?.eval_violations.length} 条）：</div>
                                  <div className="space-y-2">
                                    {ed?.eval_violations.map((v: any, i: number) => (
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
                                  {ed?.llm_soft_details && typeof ed?.llm_soft_details === 'object' && (
                                    <span className="text-gray-500">
                                      (叙事:{ed?.llm_soft_details['叙事性'] || '-'} 通顺:{ed?.llm_soft_details['通顺性'] || '-'} 故事:{ed?.llm_soft_details['故事性'] || '-'} 加粗:{ed?.llm_soft_details['加粗合理性'] || '-'} 术语:{ed?.llm_soft_details['术语通俗化'] || '-'})
                                    </span>
                                  )}
                                  {renderLayerReview(item.id, 'llm', ed?.layer_reviews?.llm)}
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
                                  {/* 逐项核对明细：裁判自证查了什么，无编造也可展开核对 */}
                                  {(item.fabrication['核对明细'] || []).length > 0 && (
                                    <details className="ml-16 mt-1">
                                      <summary className="cursor-pointer text-blue-600 hover:text-blue-800">
                                        🔍 逐项核对明细（{item.fabrication['核对明细'].length}项，点击展开裁判核对过程）
                                      </summary>
                                      <div className="mt-1 space-y-1">
                                        {item.fabrication['核对明细'].map((c: any, k: number) => (
                                          <div key={k} className="flex gap-1.5 text-xs">
                                            <span className="shrink-0">
                                              {c['结果'] === '违规' ? '❌' : c['结果'] === '通过' ? '✅' : '➖'}
                                            </span>
                                            <div>
                                              <span className={
                                                c['结果'] === '违规' ? 'text-red-600 font-medium' :
                                                c['结果'] === '通过' ? 'text-green-700 font-medium' : 'text-gray-400'
                                              }>
                                                【{c['检查项']}{c['结果'] !== '未涉及' ? `·${c['结果']}` : ''}】
                                              </span>
                                              <span className="text-gray-600">{c['说明']}</span>
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </details>
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
                        <details className="mt-1 text-xs" onToggle={(e) => { if ((e.currentTarget as HTMLDetailsElement).open) loadDetail(item.id) }}>
                          <summary className="cursor-pointer text-blue-600 hover:text-blue-800">查看报告全貌（违规段落红色标注）</summary>
                          <div className="mt-2">
                            {expandedDetail[item.id]?.loading ? (
                              <div className="p-3 bg-gray-50 rounded text-gray-500">加载报告中...</div>
                            ) : !ed?.report ? (
                              <div className="p-3 bg-gray-50 rounded text-gray-400">该记录未存完整报告（旧数据），仅显示上方预览</div>
                            ) : (
                              <div className="space-y-2">
                                {/* 开头 */}
                                {ed?.report.opening && (
                                  <div className={`rounded p-2 border ${violatedSections.has('opening') || fabSections.has('opening') ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'}`}>
                                    <div className="text-gray-400 mb-1">【开头】</div>
                                    {ed?.report.opening.lead && <div className="text-sm text-gray-800">{ed?.report.opening.lead}</div>}
                                    {ed?.report.opening.verdict && <div className="text-sm text-gray-600 mt-1">【判断】{ed?.report.opening.verdict}</div>}
                                  </div>
                                )}
                                {/* 子话题 */}
                                {(ed?.report.subtopics || []).map((sub: any, si: number) => (
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
                                {ed?.report.summary && (
                                  <div className={`rounded p-2 border ${violatedSections.has('summary') || fabSections.has('summary') ? 'border-red-400 bg-red-50' : 'border-gray-200 bg-white'}`}>
                                    <div className="text-gray-400 mb-1">【总结】</div>
                                    {(ed?.report.summary.items || []).map((it: any, k: number) => (
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
              {/* 底部分页 */}
              {productionTotal > productionPageSize && (
                <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-sm">
                  <button
                    onClick={() => { const p = Math.max(0, productionPage - 1); setProductionPage(p); loadProduction(p) }}
                    disabled={productionPage === 0}
                    className="px-3 py-1 rounded border text-xs disabled:opacity-40 hover:bg-gray-100"
                  >上一页</button>
                  <span className="text-gray-500">第 {productionPage + 1} / {Math.max(1, Math.ceil(productionTotal / productionPageSize))} 页</span>
                  <button
                    onClick={() => { const p = productionPage + 1; setProductionPage(p); loadProduction(p) }}
                    disabled={(productionPage + 1) * productionPageSize >= productionTotal}
                    className="px-3 py-1 rounded border text-xs disabled:opacity-40 hover:bg-gray-100"
                  >下一页</button>
                </div>
              )}
            </div>
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
