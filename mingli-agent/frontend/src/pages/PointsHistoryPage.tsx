import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../store/userStore'
import { paymentApi, type Transaction } from '../api/payment'

/** 根据业务类型 + 描述生成展示文案 */
function buildLabel(t: Transaction): string {
  const desc = t.description || ''
  // 充值
  if (t.biz_type === 'recharge' || t.type === 'recharge') return '充值'
  // 新用户赠送
  if (t.biz_type === 'new_user_bonus') return '新用户赠送'
  // 分享得积分
  if (t.biz_type === 'share_reward') return '分享得积分'
  // 首次报告：保留"创建人物XXX"，去掉"，生成命盘"
  if (t.biz_type === 'first_reading' || desc.startsWith('创建人物')) {
    return desc.replace('，生成命盘', '').trim() || '首次报告'
  }
  // 追问：只显示"追问"，不展示问题内容
  if (t.biz_type === 'followup' || desc.startsWith('追问')) {
    return '追问'
  }
  // 兜底
  return desc || (t.type === 'recharge' ? '充值' : '积分消耗')
}

export default function PointsHistoryPage() {
  const navigate = useNavigate()
  const { user } = useUserStore()
  const [items, setItems] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    console.log('[PointsHistory] 开始加载积分明细...')
    setLoading(true)
    setError(null)
    try {
      const { data } = await paymentApi.getTransactions(200)
      const items = data.items || []
      console.log(`[PointsHistory] 加载成功，共 ${items.length} 条记录`)
      if (items.length > 0) {
        console.log('[PointsHistory] 前3条原始数据:', items.slice(0, 3))
      }
      setItems(items)
    } catch (err: any) {
      console.error('[PointsHistory] 加载失败:', err?.response?.status, err?.response?.data || err)
      setError(err?.response?.data?.detail || '积分明细加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // 后端存的是无时区 UTC 时间，统一补 Z 解析后转本地时区展示
  const formatTime = (iso: string) => {
    const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
    const d = new Date(normalized)
    if (isNaN(d.getTime())) return iso
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  const itemLabel = (t: Transaction) => {
    const label = buildLabel(t)
    console.log(`[PointsHistory] 记录#${t.id} biz_type=${t.biz_type || 'null'} type=${t.type} desc="${t.description || ''}" → 标签=${label}`)
    return label
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* 顶部：返回 + 标题 */}
      <div className="flex items-center mb-4">
        <button
          onClick={() => navigate('/')}
          className="text-gray-500 hover:text-gray-700 p-1 mr-2 transition-colors"
          aria-label="返回"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <h1 className="text-lg font-bold text-gray-800">积分明细</h1>
      </div>

      {/* 当前积分 */}
      <div className="rounded-xl p-4 mb-4" style={{ backgroundColor: '#eceae6' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center">
            <span className="text-yellow-400 text-xl mr-2">⭐</span>
            <span className="text-gray-600 text-sm">当前积分</span>
          </div>
          <span className="text-primary-600 font-bold text-2xl">{user?.points ?? 0}</span>
        </div>
      </div>

      {/* 明细列表 */}
      <div className="bg-white rounded-xl px-4 py-2 shadow-sm">
        {/* 表头 */}
        {!loading && !error && items.length > 0 && (
          <div className="grid grid-cols-3 gap-2 py-2 border-b border-gray-100">
            <span className="text-xs text-gray-400">操作时间</span>
            <span className="text-xs text-gray-400">类型</span>
            <span className="text-xs text-gray-400 text-right">积分变化</span>
          </div>
        )}
        {loading ? (
          <div className="text-center py-12 text-gray-400 text-sm">加载中...</div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-gray-400 text-sm mb-3">{error}</p>
            <button
              onClick={load}
              className="px-4 py-2 rounded-lg border border-gray-200 text-gray-600 text-sm hover:bg-gray-50 transition-all"
            >
              重试
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-sm">暂无积分记录</p>
          </div>
        ) : (
          items.map((t) => {
            // 后端 points 字段恒存正数，方向由 type 决定：consume=扣费(-)，recharge/bonus=收入(+)
            const isPositive = t.type !== 'consume'
            console.log(`[PointsHistory] 渲染记录#${t.id} type=${t.type} points=${t.points} isPositive=${isPositive} → ${isPositive ? '+' : '-'}${Math.abs(t.points)}`)
            return (
              <div
                key={t.id}
                className="grid grid-cols-3 gap-2 py-3 border-b border-gray-50 last:border-0 items-center"
              >
                <span className="text-xs text-gray-400">{formatTime(t.created_at)}</span>
                <span className="text-sm text-gray-800">{itemLabel(t)}</span>
                <span
                  className={`text-right font-medium ${
                    isPositive ? 'text-green-500' : 'text-red-400'
                  }`}
                >
                  {isPositive ? '+' : '-'}
                  {Math.abs(t.points)}
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
