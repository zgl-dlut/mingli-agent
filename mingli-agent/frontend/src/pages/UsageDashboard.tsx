import { useState, useEffect, useCallback } from 'react'
import { adminApi, type UsageLogItem } from '../api/admin'
import AdminNav from '../components/AdminNav'

const bizTypeLabel: Record<string, string> = {
  first_reading: '首次报告',
  followup: '追问',
}

// 后端存的是无时区 UTC 时间，补 Z 解析后转本地时区展示
const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function UsageDashboard() {
  const [items, setItems] = useState<UsageLogItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [filterBizType, setFilterBizType] = useState('')
  const [filterSuccess, setFilterSuccess] = useState('')
  const [filterUserId, setFilterUserId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const limit = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await adminApi.usageLogs({
        offset,
        limit,
        biz_type: filterBizType || undefined,
        success: filterSuccess === '' ? undefined : filterSuccess === 'true',
        user_id: filterUserId ? Number(filterUserId) : undefined,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [offset, filterBizType, filterSuccess, filterUserId])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="min-h-screen bg-slate-50">
      <AdminNav />
      <div className="p-4 md:p-6 max-w-7xl mx-auto">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">📈 AI 用量记录</h1>
            <p className="text-sm text-slate-500 mt-1">
              首次报告 / 追问的字数与 token 消耗、模型、成败、用时
            </p>
          </div>
          <button
            onClick={load}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
          >
            🔄 刷新
          </button>
        </div>

        {/* 筛选器 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
            <div>
              <label className="block text-xs text-slate-500 mb-1">类型</label>
              <select
                value={filterBizType}
                onChange={(e) => { setFilterBizType(e.target.value); setOffset(0) }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">全部</option>
                <option value="first_reading">首次报告</option>
                <option value="followup">追问</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">结果</label>
              <select
                value={filterSuccess}
                onChange={(e) => { setFilterSuccess(e.target.value); setOffset(0) }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">全部</option>
                <option value="true">成功</option>
                <option value="false">失败</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">用户 ID</label>
              <input
                type="number"
                value={filterUserId}
                onChange={(e) => { setFilterUserId(e.target.value); setOffset(0) }}
                placeholder="精确匹配"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <button
              onClick={() => { setFilterBizType(''); setFilterSuccess(''); setFilterUserId(''); setOffset(0) }}
              className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm"
            >
              重置筛选
            </button>
          </div>
        </div>

        {/* 表格 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="text-sm text-slate-600">
              共 <b className="text-slate-800">{total}</b> 条记录
            </span>
          </div>
          {error ? (
            <div className="py-16 text-center text-red-400 text-sm">{error}</div>
          ) : loading ? (
            <div className="py-16 text-center text-slate-400 text-sm">加载中...</div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center text-slate-400 text-sm">暂无用量记录</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm whitespace-nowrap">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs">
                    <th className="px-3 py-2 text-left">时间</th>
                    <th className="px-3 py-2 text-left">用户</th>
                    <th className="px-3 py-2 text-left">类型</th>
                    <th className="px-3 py-2 text-right">输入字数</th>
                    <th className="px-3 py-2 text-right">输入token</th>
                    <th className="px-3 py-2 text-right">输出字数</th>
                    <th className="px-3 py-2 text-right">输出token</th>
                    <th className="px-3 py-2 text-right">总token</th>
                    <th className="px-3 py-2 text-center">命中缓存</th>
                    <th className="px-3 py-2 text-right">缓存token</th>
                    <th className="px-3 py-2 text-left">模型</th>
                    <th className="px-3 py-2 text-center">结果</th>
                    <th className="px-3 py-2 text-right">用时</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 text-slate-500">{formatTime(r.created_at)}</td>
                      <td className="px-3 py-2 text-slate-700">{r.user_name}（{r.user_id}）</td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          r.biz_type === 'first_reading'
                            ? 'bg-blue-100 text-blue-600'
                            : 'bg-amber-100 text-amber-600'
                        }`}>
                          {bizTypeLabel[r.biz_type] || r.biz_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-700">{r.input_chars}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{r.input_tokens}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{r.output_chars}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{r.output_tokens}</td>
                      <td className="px-3 py-2 text-right font-medium text-slate-800">{r.total_tokens}</td>
                      <td className="px-3 py-2 text-center">
                        {r.cached_tokens > 0 ? (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 text-green-600">
                            是{r.input_tokens > 0 ? ` ${Math.round(r.cached_tokens / r.input_tokens * 100)}%` : ''}
                          </span>
                        ) : (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-400">否</span>
                        )}
                      </td>
                      <td className={`px-3 py-2 text-right ${r.cached_tokens > 0 ? 'text-green-600 font-medium' : 'text-slate-400'}`}>{r.cached_tokens}</td>
                      <td className="px-3 py-2 text-slate-600">{r.model || '—'}</td>
                      <td className="px-3 py-2 text-center">
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          r.success ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                        }`}>
                          {r.success ? '成功' : '失败'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right text-slate-600">{(r.duration_ms / 1000).toFixed(1)}s</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* 分页 */}
          {total > limit && (
            <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                显示 {offset + 1}-{Math.min(offset + limit, total)} / {total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  disabled={offset === 0}
                  className="px-3 py-1 text-sm border border-slate-300 rounded disabled:opacity-40"
                >
                  上一页
                </button>
                <button
                  onClick={() => setOffset(offset + limit)}
                  disabled={offset + limit >= total}
                  className="px-3 py-1 text-sm border border-slate-300 rounded disabled:opacity-40"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
