import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useUserStore } from '../store/userStore'

export default function LoginPage() {
  const navigate = useNavigate()
  const { sendSmsCode, loginWithSms, isLoading, error, clearError, isLoggedIn } = useUserStore()

  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [agreed, setAgreed] = useState(false)
  const [devCodeFilled, setDevCodeFilled] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  useEffect(() => {
    if (isLoggedIn) {
      navigate('/', { replace: true })
    }
  }, [isLoggedIn, navigate])

  useEffect(() => {
    if (countdown > 0) {
      timerRef.current = setInterval(() => {
        setCountdown((prev) => prev - 1)
      }, 1000)
      return () => clearInterval(timerRef.current)
    }
  }, [countdown])

  const handleSendSms = async () => {
    if (!phone || phone.length !== 11) return
    clearError()
    try {
      const res = await sendSmsCode(phone)
      setCountdown(60)
      // 后端 mock 模式（SMS_MOCK_MODE=true）不发真实短信，直接回填验证码
      if (res?.dev_mode && res?.code) {
        setCode(res.code)
        setDevCodeFilled(true)
      }
    } catch {
      // error is set in store
    }
  }

  const handleLogin = async () => {
    if (!phone || !code) return
    if (!agreed) return
    clearError()
    try {
      await loginWithSms(phone, code)
      navigate('/', { replace: true })
    } catch {
      // error is set in store
    }
  }

  const isPhoneValid = /^1\d{10}$/.test(phone)

  return (
    <div className="min-h-screen flex items-start justify-center px-4 pt-[12vh]" style={{ backgroundColor: '#4A4E8F' }}>
      <div className="w-full max-w-sm max-md:max-w-[320px]">
        {/* 品牌标识区 */}
        <div className="mb-8 flex flex-col items-center">
          {/* 品牌锁扣：Logo + 名称 */}
          <div className="flex items-center gap-3 mb-3">
            <span className="logo-text">趣算算</span>
          </div>
          {/* 副标题：半透明标签条 */}
          <span className="px-4 py-1 bg-white/15 backdrop-blur-sm rounded-full text-primary-100 text-xs tracking-wider">
            AI命理推算 · 洞察人生
          </span>
        </div>

        {/* Login Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-6 space-y-5">
          <h2 className="text-lg font-semibold text-gray-800 text-center">手机号登录</h2>

          {/* Phone Input */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1.5">手机号</label>
            <input
              type="tel"
              maxLength={11}
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, ''))}
              placeholder="请输入手机号"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
            />
          </div>

          {/* SMS Code Input */}
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1.5">验证码</label>
            <div className="flex gap-3">
              <input
                type="text"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                placeholder="6位验证码"
                className="flex-1 min-w-0 px-4 py-3 border border-gray-200 rounded-xl text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all"
              />
              <button
                onClick={handleSendSms}
                disabled={!isPhoneValid || countdown > 0 || isLoading}
                className="px-4 py-3 rounded-xl text-sm font-medium whitespace-nowrap transition-all disabled:opacity-40 disabled:cursor-not-allowed max-md:px-3 max-md:text-xs"
                style={{
                  backgroundColor: isPhoneValid && countdown === 0 ? '#4A4E8F' : '#e5e7eb',
                  color: isPhoneValid && countdown === 0 ? 'white' : '#9ca3af',
                }}
              >
                {countdown > 0 ? `${countdown}s` : '获取验证码'}
              </button>
            </div>
            {devCodeFilled && (
              <p className="text-xs mt-1.5" style={{ color: '#4A4E8F' }}>开发模式：验证码已自动填入，直接登录即可</p>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-600 text-center">{error}</p>
            </div>
          )}

          {/* Login Button */}
          <button
            onClick={handleLogin}
            disabled={phone.length !== 11 || code.length !== 6 || isLoading || !agreed}
            className="w-full py-3.5 rounded-xl text-white font-semibold text-base transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-lg hover:shadow-xl active:scale-[0.98]"
            style={{ backgroundColor: '#4A4E8F' }}
          >
            {isLoading ? '登录中...' : '登录 / 注册'}
          </button>

          {/* Terms */}
          <div className="flex items-start gap-2">
            <button
              type="button"
              onClick={() => setAgreed(!agreed)}
              className={`mt-0.5 w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-all ${
                agreed
                  ? 'bg-primary-600 border-primary-600 text-white'
                  : 'bg-white border-gray-300 text-transparent'
              }`}
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </button>
            <p className="text-xs text-gray-500 leading-relaxed">
              我已阅读并同意
              <Link to="/legal/terms" className="text-primary-600 hover:underline">《用户服务协议》</Link>
              和
              <Link to="/legal/privacy" className="text-primary-600 hover:underline">《隐私政策》</Link>
              ，了解命理推算结果由 AI 生成，仅供参考，不构成任何建议。
            </p>
          </div>

        </div>
      </div>
    </div>
  )
}
