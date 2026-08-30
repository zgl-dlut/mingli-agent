import { useState } from 'react'
import { adminApi } from '../api/admin'
import AdminNav from '../components/AdminNav'

export default function AdminRechargePage() {
  const [phone, setPhone] = useState('')
  const [points, setPoints] = useState(100)
  const [remark, setRemark] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [lastResult, setLastResult] = useState<{
    user_name: string
    phone: string
    points_added: number
    balance: number
  } | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!phone.trim()) {
      setMessage({ type: 'error', text: '请输入手机号' })
      return
    }
    if (points < 1 || points > 100000) {
      setMessage({ type: 'error', text: '充值积分需在 1~100000 之间' })
      return
    }

    setLoading(true)
    setMessage(null)
    setLastResult(null)

    try {
      const { data } = await adminApi.rechargeByPhone({
        phone: phone.trim(),
        points,
        remark: remark.trim(),
      })
      setLastResult({
        user_name: data.user_name,
        phone: data.phone,
        points_added: data.points_added,
        balance: data.balance,
      })
      setMessage({ type: 'success', text: `充值成功！${data.user_name} 的积分已增加 ${data.points_added}，当前余额 ${data.balance}` })
      setPhone('')
      setPoints(100)
      setRemark('')
    } catch (err: any) {
      setMessage({ type: 'error', text: err?.response?.data?.detail || '充值失败，请稍后重试' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">管理员充值</h1>
          <p className="text-sm text-gray-500 mt-1">通过手机号给用户直接充值积分</p>
        </div>

        {message && (
          <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">手机号</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="请输入用户手机号"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">充值积分</label>
            <input
              type="number"
              value={points}
              onChange={(e) => setPoints(Number(e.target.value))}
              min={1}
              max={100000}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-1">范围：1 ~ 100000 积分</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">备注（可选）</label>
            <input
              type="text"
              value={remark}
              onChange={(e) => setRemark(e.target.value)}
              placeholder="充值原因或说明"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? '充值中...' : '确认充值'}
          </button>
        </form>

        {lastResult && (
          <div className="mt-6 bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">最近充值记录</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">用户姓名</span>
                <span className="text-gray-900">{lastResult.user_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">手机号</span>
                <span className="text-gray-900">{lastResult.phone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">充值积分</span>
                <span className="text-green-600 font-medium">+{lastResult.points_added}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">当前余额</span>
                <span className="text-gray-900 font-medium">{lastResult.balance}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
