import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../store/userStore'

export default function AdminLoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { setUser } = useUserStore()

  const handleLogin = async () => {
    if (!username || !password) return
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/auth/admin-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || '登录失败')
        return
      }
      localStorage.setItem('mingli_token', data.access_token)
      localStorage.setItem('mingli_admin', JSON.stringify({ username: data.username, role: data.role }))
      // 同步更新 store 状态，避免 ProtectedRoute 重定向到 /login
      setUser({
        id: 0,
        phone: '',
        name: data.username,
        avatar: null,
        points: 0,
        created_at: new Date().toISOString(),
      })
      navigate('/admin/usage', { replace: true })
    } catch {
      setError('网络错误，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: '#f5f0eb' }}>
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-2xl shadow-xl p-8 space-y-6">
          <div className="text-center">
            <h1 className="text-xl font-bold text-gray-800">管理后台登录</h1>
            <p className="text-sm text-gray-500 mt-1">趣算算 · 管理系统</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1.5">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#a7876f] focus:border-transparent"
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1.5">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#a7876f] focus:border-transparent"
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-600 text-center">{error}</p>
            </div>
          )}

          <button
            onClick={handleLogin}
            disabled={loading || !username || !password}
            className="w-full py-3.5 rounded-xl text-white font-semibold text-base transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg hover:shadow-xl active:scale-[0.98]"
            style={{ backgroundColor: '#a7876f' }}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </div>
      </div>
    </div>
  )
}
