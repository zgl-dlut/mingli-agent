import { useState, useEffect, useCallback } from 'react'
import { adminApi, type UserPointsItem } from '../api/admin'
import AdminNav from '../components/AdminNav'

// 后端存的是无时区 UTC 时间，补 Z 解析后转本地时区展示
const formatTime = (iso: string | null) => {
  if (!iso) return '—'
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function AdminUsersPage() {
  const [items, setItems] = useState<UserPointsItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const limit = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await adminApi.usersPoints({
        offset,
        limit,
        search: search || undefined,
      })
      setItems(data.items || [])
      setTotal(data.total)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [offset, search])

  useEffect(() => {
    load()
  }, [load])

  const doSearch = () => {
    setOffset(0)
    setSearch(searchInput.trim())
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <AdminNav />
      <div className="p-4 md:p-6 max-w-7xl mx-auto">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">👥 用户积分</h1>
            <p className="text-sm text-slate-500 mt-1">
              注册情况与积分赠送、充值、消耗总览（已充值仅含用户自己付费，不含管理员充值）
            </p>
          </div>
          <button
            onClick={load}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
          >
            🔄 刷新
          </button>
        </div>

        {/* 搜索 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
          <div className="flex gap-3 items-center">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && doSearch()}
              placeholder="搜索手机号或用户名"
              className="flex-1 max-w-xs border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
            <button
              onClick={doSearch}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
            >
              搜索
            </button>
            <button
              onClick={() => { setSearchInput(''); setOffset(0); setSearch('') }}
              className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm"
            >
              重置
            </button>
          </div>
        </div>

        {/* 表格 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200">
            <span className="text-sm text-slate-600">
              共 <b className="text-slate-800">{total}</b> 位用户
            </span>
          </div>
          {error ? (
            <div className="py-16 text-center text-red-400 text-sm">{error}</div>
          ) : loading ? (
            <div className="py-16 text-center text-slate-400 text-sm">加载中...</div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center text-slate-400 text-sm">暂无用户</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm whitespace-nowrap">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs">
                    <th className="px-3 py-2 text-left">用户名</th>
                    <th className="px-3 py-2 text-left">手机号</th>
                    <th className="px-3 py-2 text-right">注册赠送</th>
                    <th className="px-3 py-2 text-right">已充值</th>
                    <th className="px-3 py-2 text-right">已消耗</th>
                    <th className="px-3 py-2 text-right">当前余额</th>
                    <th className="px-3 py-2 text-left">注册时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((u) => (
                    <tr key={u.user_id} className="hover:bg-slate-50">
                      <td className="px-3 py-2 text-slate-700 font-medium">
                        {u.name}
                        <span className="text-slate-400 text-xs ml-1">#{u.user_id}</span>
                      </td>
                      <td className="px-3 py-2 text-slate-600">{u.phone}</td>
                      <td className="px-3 py-2 text-right text-amber-600">{u.bonus_total || '—'}</td>
                      <td className="px-3 py-2 text-right text-green-600">{u.recharge_total || '—'}</td>
                      <td className="px-3 py-2 text-right text-slate-700">{u.consumed_total || '—'}</td>
                      <td className="px-3 py-2 text-right text-blue-600 font-medium">{u.balance}</td>
                      <td className="px-3 py-2 text-slate-500">{formatTime(u.created_at)}</td>
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
