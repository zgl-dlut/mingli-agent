import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

interface EvalMethodologyProps {
  typeDistribution?: Array<{ name: string; value: number; color: string }>
  latestResult?: any
  versions?: Array<{ id: number; name: string; created_at: string; eval_type?: string }>
  allItems?: any[]
}

export default function EvalMethodology({ typeDistribution = [], latestResult, versions = [], allItems = [] }: EvalMethodologyProps) {
  const formatTime = (iso: string) => {
    const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
    const d = new Date(normalized)
    if (isNaN(d.getTime())) return iso
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  }

  return (
    <div className="space-y-6">
      {/* 评测体系全景图 */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-6 border border-blue-200">
        <h2 className="text-lg font-bold text-gray-900 mb-4"> AI 产品评测体系全景</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* 实验室评测 */}
          <div className="bg-white rounded-lg p-4 shadow-sm border border-blue-200">
            <div className="text-2xl mb-2"></div>
            <h3 className="font-semibold text-blue-900 mb-2">实验室评测</h3>
            <p className="text-sm text-gray-600 mb-3">预定义用例，有预期结果</p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li>✓ 结构检查（子问题覆盖、block 数量）</li>
              <li>✓ 叙事检查（术语黑名单、回避式表达）</li>
              <li>✓ 命盘使用检查（用神一致性、编造检测）</li>
              <li>✓ 用于回归测试，防止修复后再次出错</li>
            </ul>
          </div>

          {/* 生产监控 */}
          <div className="bg-white rounded-lg p-4 shadow-sm border border-purple-200">
            <div className="text-2xl mb-2">📊</div>
            <h3 className="font-semibold text-purple-900 mb-2">生产监控</h3>
            <p className="text-sm text-gray-600 mb-3">真实用户报告，智能采样</p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li>✓ 第一层：规则检测（100% 覆盖，零成本）</li>
              <li>✓ 第二层：轻量指标（100% 覆盖，低成本）</li>
              <li>✓ 第三层：LLM 深度评测（智能抽样）</li>
              <li>✓ 用于发现未知问题，持续改进</li>
            </ul>
          </div>

          {/* 持续改进 */}
          <div className="bg-white rounded-lg p-4 shadow-sm border border-green-200">
            <div className="text-2xl mb-2">🔄</div>
            <h3 className="font-semibold text-green-900 mb-2">持续改进</h3>
            <p className="text-sm text-gray-600 mb-3">问题定位 → Prompt 修复 → 回归验证</p>
            <ul className="text-xs text-gray-500 space-y-1">
              <li>✓ 定位问题根因（术语堆砌、编造、跑题）</li>
              <li>✓ 修复 Prompt 或检查器</li>
              <li>✓ 重新运行评测集验证</li>
              <li>✓ 部署后生产监控确认效果</li>
            </ul>
          </div>
        </div>

        {/* 流程箭头 */}
        <div className="hidden md:flex justify-center items-center mt-4 text-gray-400">
          <span className="text-2xl">🧪</span>
          <span className="mx-4 text-xl">→</span>
          <span className="text-2xl">📊</span>
          <span className="mx-4 text-xl">→</span>
          <span className="text-2xl">🔄</span>
        </div>
      </div>

      {/* 三层检测体系 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">🔍 三层检测体系</h2>
        <div className="space-y-4">
          {/* 第一层 */}
          <div className="border-l-4 border-green-500 pl-4 py-2">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-900">第一层：规则检测</h3>
              <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">100% 覆盖 · 零成本</span>
            </div>
            <p className="text-sm text-gray-600 mb-2">基于正则表达式的快速检测，每次生成后自动执行</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="text-xs bg-gray-50 rounded p-2">术语黑名单</div>
              <div className="text-xs bg-gray-50 rounded p-2">干支纪时写法</div>
              <div className="text-xs bg-gray-50 rounded p-2">凶年启动检测</div>
              <div className="text-xs bg-gray-50 rounded p-2">同义词对立</div>
            </div>
          </div>

          {/* 第二层 */}
          <div className="border-l-4 border-blue-500 pl-4 py-2">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-900">第二层：轻量指标</h3>
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">100% 覆盖 · 低成本</span>
            </div>
            <p className="text-sm text-gray-600 mb-2">自动计算，不调 LLM，异常信号触发深度检测</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="text-xs bg-gray-50 rounded p-2">字数 &lt; 300</div>
              <div className="text-xs bg-gray-50 rounded p-2">block &lt; 1</div>
              <div className="text-xs bg-gray-50 rounded p-2">生成 &lt; 3 秒</div>
              <div className="text-xs bg-gray-50 rounded p-2">生成 &gt; 600 秒</div>
            </div>
          </div>

          {/* 第三层 */}
          <div className="border-l-4 border-purple-500 pl-4 py-2">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-900">第三层：LLM 深度评测</h3>
              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded">智能抽样 · 按需调用</span>
            </div>
            <p className="text-sm text-gray-600 mb-2">只在以下情况触发，避免浪费 LLM 调用</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
              <div className="text-xs bg-red-50 border border-red-200 rounded p-2">
                <strong>高风险必检</strong><br/>
                敏感话题、负面情绪、首次报告
              </div>
              <div className="text-xs bg-yellow-50 border border-yellow-200 rounded p-2">
                <strong>异常触发</strong><br/>
                规则违规、指标异常、用户投诉
              </div>
              <div className="text-xs bg-gray-50 border border-gray-200 rounded p-2">
                <strong>随机兜底</strong><br/>
                5% 随机采样，发现未知问题
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 评测指标字典 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">📐 评测指标字典</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">层级</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">指标</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">含义</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">怎么算</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">合格线</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800">总</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">检测准确率</td>
                <td className="px-4 py-3 text-sm text-gray-600">预期结果与实际结果匹配的比例</td>
                <td className="px-4 py-3 text-sm text-gray-600">预期失败 + 实际失败 = 通过<br/>预期通过 + 实际通过 = 通过</td>
                <td className="px-4 py-3 text-sm"><span className="text-green-600 font-medium">≥ 80%</span></td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-800">总</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">通过率</td>
                <td className="px-4 py-3 text-sm text-gray-600">通过硬性检查的报告比例</td>
                <td className="px-4 py-3 text-sm text-gray-600">0 违规 = 通过<br/>1+ 违规 = 失败</td>
                <td className="px-4 py-3 text-sm"><span className="text-yellow-600 font-medium">≥ 60%</span></td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-800">L1</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">技术完成</td>
                <td className="px-4 py-3 text-sm text-gray-600">JSON 解析 + Pydantic 校验通过</td>
                <td className="px-4 py-3 text-sm text-gray-600">无 json_parse_error / pydantic_validation_error</td>
                <td className="px-4 py-3 text-sm"><span className="text-green-600 font-medium">≥ 95%</span></td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-cyan-100 text-cyan-800">L2</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">格式完成</td>
                <td className="px-4 py-3 text-sm text-gray-600">结构检查通过</td>
                <td className="px-4 py-3 text-sm text-gray-600">无子问题漏答、block数量异常、keyword为空、narrative过短/过长、summary关键词泛泛等</td>
                <td className="px-4 py-3 text-sm"><span className="text-green-600 font-medium">≥ 90%</span></td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-800">L3</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">质量完成</td>
                <td className="px-4 py-3 text-sm text-gray-600">叙事检查 + 命盘使用检查通过</td>
                <td className="px-4 py-3 text-sm text-gray-600">无术语黑名单、编造大运/流年、用神不一致等违规</td>
                <td className="px-4 py-3 text-sm"><span className="text-yellow-600 font-medium">≥ 75%</span></td>
              </tr>
              <tr>
                <td className="px-4 py-3 text-sm"><span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-800">L4</span></td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">综合完成</td>
                <td className="px-4 py-3 text-sm text-gray-600">L1×L2×L3 全部通过</td>
                <td className="px-4 py-3 text-sm text-gray-600">四层检查都通过 = 完成<br/>任一层失败 = 未完成</td>
                <td className="px-4 py-3 text-sm"><span className="text-yellow-600 font-medium">≥ 70%</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 数据来源说明 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">📦 数据来源说明</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
            <div className="flex items-center mb-2">
              <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-800 font-medium mr-2">实验室</span>
              <h3 className="font-medium text-blue-900">实验室评测</h3>
            </div>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• 来源：预定义用例（eval_dataset.json）</li>
              <li>• 特点：有预期结果（通过/失败）</li>
              <li>• 用途：回归测试，防止修复后再次出错</li>
              <li>• 类型：report_quality / chart_accuracy / badcase_eval</li>
            </ul>
          </div>

          <div className="border border-purple-200 rounded-lg p-4 bg-purple-50">
            <div className="flex items-center mb-2">
              <span className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-800 font-medium mr-2">生产</span>
              <h3 className="font-medium text-purple-900">生产监控</h3>
            </div>
            <ul className="text-sm text-gray-600 space-y-1">
              <li>• 来源：真实用户生成的报告</li>
              <li>• 特点：无预期结果，智能采样后 LLM 评测</li>
              <li>• 用途：发现未知问题，持续改进</li>
              <li>• 类型：production_monitor</li>
            </ul>
          </div>
        </div>
      </div>

      {/* 评测类型分布（如果有数据） */}
      {typeDistribution.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">📊 评测类型分布</h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={typeDistribution}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry) => `${entry.name}: ${entry.value}`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {typeDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 核心指标卡片（如果有最新版本数据） */}
      {latestResult && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">📈 最新版本指标</h2>
          {/* 总指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">
                {((latestResult.match_rate || 0) * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-500 mt-1">检测准确率（总）</div>
              <div className="text-xs text-gray-400">
                ({latestResult.match_count}/{latestResult.total})
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">
                {((latestResult.pass_rate || 0) * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-500 mt-1">通过率（总）</div>
              <div className="text-xs text-gray-400">
                ({latestResult.passed}/{latestResult.total})
              </div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-cyan-600">
                {latestResult.format_pass_rate != null
                  ? `${(latestResult.format_pass_rate * 100).toFixed(1)}%`
                  : '-'}
              </div>
              <div className="text-sm text-gray-500 mt-1">L2 格式</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">
                {latestResult.task_completion_rate?.overall != null
                  ? `${(latestResult.task_completion_rate.overall * 100).toFixed(1)}%`
                  : '-'}
              </div>
              <div className="text-sm text-gray-500 mt-1">L4 综合</div>
            </div>
          </div>
          {/* L1-L4 分层明细 */}
          {latestResult.task_completion_rate && (
            <div className="border-t border-gray-200 pt-4">
              <div className="text-sm font-medium text-gray-700 mb-3">分层明细</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">L1 技术完成</div>
                  <div className="text-xl font-bold text-green-600">
                    {latestResult.task_completion_rate.l1_technical != null
                      ? `${(latestResult.task_completion_rate.l1_technical * 100).toFixed(1)}%`
                      : '-'}
                  </div>
                  <div className="text-xs text-gray-400">JSON解析 + Pydantic校验</div>
                </div>
                <div className="text-center bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">L2 格式完成</div>
                  <div className="text-xl font-bold text-cyan-600">
                    {latestResult.task_completion_rate.l2_format != null
                      ? `${(latestResult.task_completion_rate.l2_format * 100).toFixed(1)}%`
                      : '-'}
                  </div>
                  <div className="text-xs text-gray-400">结构检查（子问题/block/narrative）</div>
                </div>
                <div className="text-center bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">L3 质量完成</div>
                  <div className="text-xl font-bold text-yellow-600">
                    {latestResult.task_completion_rate.l3_quality != null
                      ? `${(latestResult.task_completion_rate.l3_quality * 100).toFixed(1)}%`
                      : '-'}
                  </div>
                  <div className="text-xs text-gray-400">叙事检查 + 命盘使用检查</div>
                </div>
                <div className="text-center bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">L4 综合完成</div>
                  <div className="text-xl font-bold text-purple-600">
                    {latestResult.task_completion_rate.l4_satisfaction != null
                      ? `${(latestResult.task_completion_rate.l4_satisfaction * 100).toFixed(1)}%`
                      : '-'}
                  </div>
                  <div className="text-xs text-gray-400">L1×L2×L3 全部通过</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 最近评测列表 */}
      {versions.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900"> 最近评测</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">版本</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">类型</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">来源</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">检测准确率</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">通过率</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">时间</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {versions.slice(0, 10).map((version) => {
                  const item = allItems.find(v => v.id === version.id)
                  const type = item?.eval_type || 'report_quality'
                  const typeMap: Record<string, { label: string; color: string }> = {
                    report_quality: { label: '报告质量', color: '#3b82f6' },
                    chart_accuracy: { label: '排盘正确性', color: '#10b981' },
                    badcase_eval: { label: 'Badcase', color: '#f59e0b' },
                    production_monitor: { label: '生产监控', color: '#8b5cf6' },
                  }
                  const typeInfo = typeMap[type] || { label: type, color: '#6b7280' }
                  const isLab = ['report_quality', 'chart_accuracy', 'badcase_eval'].includes(type)

                  return (
                    <tr key={version.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">v{version.id}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: `${typeInfo.color}15`, color: typeInfo.color }}>
                          {typeInfo.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <span className={`text-xs px-2 py-0.5 rounded ${isLab ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'}`}>
                          {isLab ? '实验室' : '生产'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item ? `${((item.match_rate || 0) * 100).toFixed(1)}%` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {item ? `${((item.pass_rate || 0) * 100).toFixed(1)}%` : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatTime(version.created_at)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
