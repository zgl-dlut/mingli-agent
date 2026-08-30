import { useState, useEffect } from 'react'
import { adminApi } from '../api/admin'
import AdminNav from '../components/AdminNav'

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function PromptVersionPage() {
  const [versions, setVersions] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [message, setMessage] = useState('')

  const loadVersions = async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.promptVersions()
      setVersions(data.items || [])
      setTotal(data.total || 0)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadVersions()
  }, [])

  const handleRollback = async (versionId: number) => {
    if (!confirm('确定要回滚到此版本吗？此操作会影响所有新生成的报告。')) return
    try {
      await adminApi.rollbackPromptVersion(versionId)
      setMessage('回滚请求已提交，请手动将 prompt 内容写回 followup_structured.py')
    } catch (err: any) {
      setMessage('回滚失败: ' + (err?.response?.data?.detail || '未知错误'))
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 头部 */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Prompt 版本历史</h1>
          <p className="text-sm text-gray-500 mt-1">
            记录每次规则注入的 prompt 变更，支持回滚到任意版本
          </p>
        </div>

        {message && (
          <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.includes('失败') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {message}
          </div>
        )}

        {/* 版本列表 */}
        {loading ? (
          <div className="text-center py-12 text-gray-500">加载中...</div>
        ) : versions.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            暂无版本记录。首次注入规则后会自动创建版本。
          </div>
        ) : (
          <div className="space-y-4">
            {versions.map((version, idx) => (
              <div key={version.id} className="bg-white rounded-lg shadow">
                {/* 版本头部 */}
                <div
                  className="p-6 cursor-pointer hover:bg-gray-50"
                  onClick={() => setExpandedId(expandedId === version.id ? null : version.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono bg-blue-100 text-blue-700 px-2 py-1 rounded">
                        {version.version}
                      </span>
                      <span className="text-sm text-gray-500">
                        #{version.id} · {formatTime(version.created_at)}
                      </span>
                      {idx === 0 && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                          最新版本
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      {expandedId === version.id ? '收起' : '展开'}
                    </span>
                  </div>

                  {version.change_summary && (
                    <div className="mt-3 text-sm text-gray-700">
                      {version.change_summary}
                    </div>
                  )}

                  {version.changed_rules?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {version.changed_rules.map((rule: any, rIdx: number) => (
                        <span
                          key={rIdx}
                          className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded"
                        >
                          {rule.category}: {rule.rule?.substring(0, 30)}...
                        </span>
                      ))}
                    </div>
                  )}

                  {version.related_badcases?.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-gray-500">关联 badcase：</span>
                      {version.related_badcases.map((bid: number) => (
                        <span key={bid} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded ml-1">
                          #{bid}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* 展开详情 */}
                {expandedId === version.id && (
                  <div className="px-6 pb-6 border-t border-gray-100 pt-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-gray-700">Prompt 内容</h3>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleRollback(version.id)
                        }}
                        className="px-3 py-1.5 bg-orange-50 text-orange-700 rounded text-xs hover:bg-orange-100"
                      >
                        回滚到此版本
                      </button>
                    </div>
                    <pre className="bg-gray-50 rounded-lg p-4 text-xs text-gray-700 overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap">
                      {version.prompt_content || '无内容'}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 统计 */}
        {!loading && versions.length > 0 && (
          <div className="mt-6 text-center text-sm text-gray-500">
            共 {total} 个版本
          </div>
        )}
      </div>
    </div>
  )
}
