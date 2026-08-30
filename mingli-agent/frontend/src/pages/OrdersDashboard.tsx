import { useState, useEffect, useCallback } from 'react'
import { adminApi, type OrderItem } from '../api/admin'
import AdminNav from '../components/AdminNav'

const statusLabel: Record<string, { text: string; cls: string }> = {
  pending: { text: '待支付', cls: 'bg-amber-100 text-amber-600' },
  paid: { text: '已支付', cls: 'bg-green-100 text-green-600' },
  cancelled: { text: '已取消', cls: 'bg-slate-100 text-slate-500' },
}

const payMethodLabel: Record<string, string> = {
  wechat: '微信支付',
  alipay: '支付宝',
}

// 后端存的是无时区 UTC 时间，补 Z 解析后转本地时区展示
const formatTime = (iso: string | null) => {
  if (!iso) return '—'
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function OrdersDashboard() {
  const [items, setItems] = useState<OrderItem[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [filterStatus, setFilterStatus] = useState('')
  const [filterUserId, setFilterUserId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const limit = 20

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await adminApi.orders({
        offset,
        limit,
        status: filterStatus || undefined,
        user_id: filterUserId ? Number(filterUserId) : undefined,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err: any) {
      setError(err?.response?.data?.detail || '加载失败')
    } finally {
      setLoading(false)
    }
  }, [offset, filterStatus, filterUserId])

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
            <h1 className="text-2xl font-bold text-slate-800">💰 订单记录</h1>
            <p className="text-sm text-slate-500 mt-1">微信支付充值订单（key 审批通过前为 mock 订单）</p>
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
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 items-end">
            <div>
              <label className="block text-xs text-slate-500 mb-1">状态</label>
              <select
                value={filterStatus}
                onChange={(e) => { setFilterStatus(e.target.value); setOffset(0) }}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="">全部</option>
                <option value="pending">待支付</option>
                <option value="paid">已支付</option>
                <option value="cancelled">已取消</option>
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
              onClick={() => { setFilterStatus(''); setFilterUserId(''); setOffset(0) }}
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
              共 <b className="text-slate-800">{total}</b> 条订单
            </span>
          </div>
          {error ? (
            <div className="py-16 text-center text-red-400 text-sm">{error}</div>
          ) : loading ? (
            <div className="py-16 text-center text-slate-400 text-sm">加载中...</div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center text-slate-400 text-sm">暂无订单记录</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm whitespace-nowrap">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 text-xs">
                    <th className="px-3 py-2 text-left">订单号</th>
                    <th className="px-3 py-2 text-left">下单时间</th>
                    <th className="px-3 py-2 text-left">用户</th>
                    <th className="px-3 py-2 text-right">积分</th>
                    <th className="px-3 py-2 text-right">金额（元）</th>
                    <th className="px-3 py-2 text-left">支付方式</th>
                    <th className="px-3 py-2 text-center">状态</th>
                    <th className="px-3 py-2 text-left">流水号</th>
                    <th className="px-3 py-2 text-left">支付时间</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map((o) => {
                    const st = statusLabel[o.status] || { text: o.status, cls: 'bg-slate-100 text-slate-500' }
                    return (
                      <tr key={o.id} className="hover:bg-slate-50">
                        <td className="px-3 py-2 text-slate-700 font-medium">#{o.id}</td>
                        <td className="px-3 py-2 text-slate-500">{formatTime(o.created_at)}</td>
                        <td className="px-3 py-2 text-slate-700">{o.user_name}（{o.user_id}）</td>
                        <td className="px-3 py-2 text-right text-slate-700">{o.points}</td>
                        <td className="px-3 py-2 text-right text-slate-700">¥{o.amount}</td>
                        <td className="px-3 py-2 text-slate-600">{payMethodLabel[o.pay_method] || o.pay_method}</td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${st.cls}`}>{st.text}</span>
                        </td>
                        <td className="px-3 py-2 text-slate-500 text-xs">{o.trade_no || '—'}</td>
                        <td className="px-3 py-2 text-slate-500">{formatTime(o.paid_at)}</td>
                      </tr>
                    )
                  })}
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
