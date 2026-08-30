/**
 * EvalDashboard 测试页面
 * 使用 Mock 数据验证版本切换和指标趋势显示
 */

import { useState, useEffect } from 'react'
import { adminApi, type EvalResultItem } from '../api/admin'
import MetricCard from '../components/MetricCard'
import VersionSelector from '../components/VersionSelector'

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

export default function EvalDashboardTest() {
  console.log('[EvalDashboardTest] 组件渲染')

  // 版本选择 & 指标卡片
  const [versions, setVersions] = useState<Array<{ id: number; name: string; created_at: string; eval_type?: string }>>([])
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)
  const [selectedResult, setSelectedResult] = useState<EvalResultItem | null>(null)
  const [trendMatchRate, setTrendMatchRate] = useState<Array<{ version: string; value: number }>>([])
  const [trendPassRate, setTrendPassRate] = useState<Array<{ version: string; value: number }>>([])
  const [trendFormatRate, setTrendFormatRate] = useState<Array<{ version: string; value: number }>>([])
  const [trendTaskCompletion, setTrendTaskCompletion] = useState<Array<{ version: string; value: number }>>([])

  // 评测结果列表
  const [items, setItems] = useState<EvalResultItem[]>([])

  // ─── 加载版本列表 & 趋势数据 ───
  const loadVersions = async () => {
    console.log('[EvalDashboardTest] 开始加载版本列表和趋势数据')
    try {
      const { data } = await adminApi.evalResults({ offset: 0, limit: 100 })
      console.log('[EvalDashboardTest] 版本列表加载成功', {
        totalVersions: data.items.length,
        latestVersion: data.items[0] ? {
          id: data.items[0].id,
          eval_type: data.items[0].eval_type,
          match_rate: data.items[0].match_rate,
        } : null
      })

      const vList = data.items.map((item: EvalResultItem) => ({
        id: item.id,
        name: `v${item.id}`,
        created_at: item.created_at,
        eval_type: item.eval_type,
      }))
      setVersions(vList)
      setItems(data.items)
      console.log('[EvalDashboardTest] 版本列表已设置', {
        versionCount: vList.length,
        versions: vList.slice(0, 3).map(v => `${v.name}(${v.eval_type})`)
      })

      // 默认选最新版本
      if (vList.length > 0 && selectedVersion === null) {
        console.log('[EvalDashboardTest] 自动选择最新版本', { versionId: vList[0].id })
        setSelectedVersion(vList[0].id)
      }

      // 构建趋势数据（最近 10 个版本，时间从早到晚）
      const recent = data.items.slice(0, 10).reverse()
      const matchRateTrend = recent.map(r => ({
        version: `v${r.id}`,
        value: parseFloat(((r.match_rate || 0) * 100).toFixed(1)),
      }))
      const passRateTrend = recent.map(r => ({
        version: `v${r.id}`,
        value: parseFloat(((r.pass_rate || 0) * 100).toFixed(1)),
      }))
      const formatRateTrend = recent.map(r => ({
        version: `v${r.id}`,
        value: r.format_pass_rate != null ? parseFloat((r.format_pass_rate * 100).toFixed(1)) : 0,
      }))
      const taskCompletionTrend = recent.map(r => ({
        version: `v${r.id}`,
        value: r.task_completion_rate?.overall != null ? parseFloat((r.task_completion_rate.overall * 100).toFixed(1)) : 0,
      }))

      console.log('[EvalDashboardTest] 趋势数据构建完成', {
        matchRatePoints: matchRateTrend.length,
        passRatePoints: passRateTrend.length,
        formatRatePoints: formatRateTrend.length,
        taskCompletionPoints: taskCompletionTrend.length,
        latestMatchRate: matchRateTrend[matchRateTrend.length - 1]?.value,
        latestPassRate: passRateTrend[passRateTrend.length - 1]?.value,
        latestFormatRate: formatRateTrend[formatRateTrend.length - 1]?.value,
        latestTaskCompletion: taskCompletionTrend[taskCompletionTrend.length - 1]?.value,
      })

      setTrendMatchRate(matchRateTrend)
      setTrendPassRate(passRateTrend)
      setTrendFormatRate(formatRateTrend)
      setTrendTaskCompletion(taskCompletionTrend)
    } catch (err) {
      console.error('[EvalDashboardTest] 版本列表加载失败', err)
    }
  }

  // ─── 加载选中版本的详情 ───
  const loadVersionDetail = async (versionId: number) => {
    console.log('[EvalDashboardTest] 开始加载版本详情', { versionId })
    try {
      const { data } = await adminApi.evalResultDetail(versionId)
      console.log('[EvalDashboardTest] 版本详情加载成功', {
        versionId: data.id,
        eval_type: data.eval_type,
        match_rate: data.match_rate,
        pass_rate: data.pass_rate,
        format_pass_rate: data.format_pass_rate,
      })
      setSelectedResult(data)
    } catch (err) {
      console.error('[EvalDashboardTest] 版本详情加载失败', { versionId, err })
      setSelectedResult(null)
    }
  }

  // 初始加载版本列表
  useEffect(() => {
    loadVersions()
  }, [])

  // 选中版本变化时加载详情
  useEffect(() => {
    if (selectedVersion !== null) {
      loadVersionDetail(selectedVersion)
    }
  }, [selectedVersion])

  // 计算 delta（当前版本 vs 上一版本）
  const getDelta = (currentVal: number, trend: Array<{ version: string; value: number }>) => {
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
    console.log('[EvalDashboardTest] 版本选择变更', { versionId })
    setSelectedVersion(versionId)
  }

  // 当前选中版本的指标值
  const currentMatchRate = selectedResult ? parseFloat(((selectedResult.match_rate || 0) * 100).toFixed(1)) : 0
  const currentPassRate = selectedResult ? parseFloat(((selectedResult.pass_rate || 0) * 100).toFixed(1)) : 0
  const currentFormatRate = selectedResult?.format_pass_rate != null
    ? parseFloat((selectedResult.format_pass_rate * 100).toFixed(1))
    : 0
  const currentTaskCompletion = selectedResult?.task_completion_rate?.overall != null
    ? parseFloat((selectedResult.task_completion_rate.overall * 100).toFixed(1))
    : 0

  console.log('[EvalDashboardTest] 渲染数据', {
    versionsCount: versions.length,
    selectedVersion,
    selectedResult: selectedResult ? {
      id: selectedResult.id,
      match_rate: selectedResult.match_rate,
    } : null,
    trendMatchRateLength: trendMatchRate.length,
    currentMatchRate,
    currentPassRate,
    currentFormatRate,
  })

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">评测中心测试页面（Mock 数据）</h1>
          <p className="text-sm text-gray-500 mt-1">验证版本切换和指标趋势显示</p>
        </div>

        {/* 版本选择器 */}
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
              trend={trendMatchRate}
              delta={getDelta(currentMatchRate, trendMatchRate)}
              color="#3b82f6"
              description="预期结果与实际结果匹配的比例"
            />
            <MetricCard
              title="通过率（总）"
              value={currentPassRate}
              unit="%"
              trend={trendPassRate}
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
              trend={trendFormatRate}
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
              trend={trendTaskCompletion}
              delta={getDelta(currentTaskCompletion, trendTaskCompletion)}
              color="#8b5cf6"
              description="L1×L2×L3 全部通过"
            />
          </div>
        </div>

        {/* 评测结果列表 */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">评测结果列表</h2>
          </div>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">评测类型</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">检测准确率</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">通过率</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L1技术</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L2格式</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">L3质量</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">创建时间</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {items.map(item => {
                const type = item.eval_type || 'report_quality'
                const typeInfo = EVAL_TYPE_MAP[type]
                return (
                  <tr
                    key={item.id}
                    className={`hover:bg-gray-50 ${selectedVersion === item.id ? 'bg-blue-50' : ''}`}
                  >
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
                      <span className={item.match_rate >= 0.8 ? 'text-green-600 font-medium' : item.match_rate >= 0.6 ? 'text-yellow-600 font-medium' : 'text-red-600 font-medium'}>
                        {((item.match_rate || 0) * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <span className={item.pass_rate >= 0.8 ? 'text-green-600' : item.pass_rate >= 0.6 ? 'text-yellow-600' : 'text-red-600'}>
                        {((item.pass_rate || 0) * 100).toFixed(1)}%
                      </span>
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
                      {item.format_pass_rate != null ? (
                        <span className={item.format_pass_rate >= 0.9 ? 'text-green-600' : item.format_pass_rate >= 0.7 ? 'text-yellow-600' : 'text-red-600'}>
                          {(item.format_pass_rate * 100).toFixed(1)}%
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
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
