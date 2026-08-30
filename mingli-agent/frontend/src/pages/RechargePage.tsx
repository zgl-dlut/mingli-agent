import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../store/userStore'
import { useTransactionStore } from '../store/transactionStore'
import { paymentApi } from '../api/payment'
import { isWechatBrowser, isMobileBrowser, wxChooseWXPay, ensureWechatOpenid, getAuthToken } from '../utils/wechat'
import QRCode from 'qrcode'

const rechargeOptions = [
  { points: 160, amount: 16 },
  { points: 200, amount: 20 },
  { points: 400, amount: 40 },
  { points: 800, amount: 80 },
  { points: 1000, amount: 100 },
  { points: 2000, amount: 200 },
]

export default function RechargePage() {
  const navigate = useNavigate()
  const { user, fetchUserInfo } = useUserStore()
  const { addTransaction } = useTransactionStore()
  const [selectedPoints, setSelectedPoints] = useState(160)
  const [isLoading, setIsLoading] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [customPoints, setCustomPoints] = useState('')
  const [isCustomMode, setIsCustomMode] = useState(false)
  const [userOpenid, setUserOpenid] = useState<string | null>(null)
  const [qrCodeUrl, setQrCodeUrl] = useState<string | null>(null)
  const [qrExpired, setQrExpired] = useState(false)
  const qrCanvasRef = useRef<HTMLCanvasElement>(null)

  const MIN_POINTS = 10
  const MAX_POINTS = 10000

  // 处理 OAuth 回调后的 token
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const tokenFromUrl = urlParams.get('token')
    if (tokenFromUrl) {
      localStorage.setItem('mingli_token', tokenFromUrl)
      // 清除 URL 中的 token 参数
      window.history.replaceState({}, '', '/recharge')
      // 重新获取用户信息
      fetchUserInfo()
    }
  }, [])

  // 微信浏览器内：检查是否已有 openid，没有则引导 OAuth 授权
  useEffect(() => {
    if (isWechatBrowser) {
      const token = getAuthToken()
      if (token) {
        ensureWechatOpenid(token).then((openid) => {
          if (openid) setUserOpenid(openid)
          // 没有 openid 时 ensureWechatOpenid 内部已跳转 OAuth，页面会刷新
        })
      }
    }
  }, [])

  // 当 qrCodeUrl 设置后，canvas 渲染到 DOM，生成二维码
  useEffect(() => {
    if (qrCodeUrl && qrCanvasRef.current) {
      QRCode.toCanvas(qrCanvasRef.current, qrCodeUrl, {
        width: 240,
        margin: 2,
        color: { dark: '#363330', light: '#ffffff' },
      }).catch((err) => {
        console.error('[RechargePage] 二维码生成失败:', err)
      })
    }
  }, [qrCodeUrl])

  const customPointsNum = parseInt(customPoints, 10)
  const isCustomValid = !isNaN(customPointsNum) && customPointsNum >= MIN_POINTS && customPointsNum <= MAX_POINTS && customPoints.toString() === String(customPointsNum)
  const effectivePoints = isCustomMode ? (isCustomValid ? customPointsNum : 0) : selectedPoints

  const handleSelectPreset = (points: number) => {
    setIsCustomMode(false)
    setCustomPoints('')
    setSelectedPoints(points)
  }

  const handleCustomInput = (value: string) => {
    const cleaned = value.replace(/\D/g, '')
    setCustomPoints(cleaned)
    setIsCustomMode(true)
  }

  const handleRecharge = async () => {
    if (effectivePoints === 0) return
    setIsLoading(true)
    setQrCodeUrl(null)

    console.log('[Recharge] points=', effectivePoints, 'custom=', isCustomMode, customPointsNum)
    try {
      const payType = isWechatBrowser ? 'jsapi' : isMobileBrowser ? 'h5' : 'native'

      // JSAPI 兜底：openid 缺失时先走 OAuth 授权，授权后页面刷新再回来充值
      let currentOpenid = userOpenid
      if (payType === 'jsapi') {
        const token = getAuthToken()
        if (!token) {
          alert('请先登录后再充值')
          setIsLoading(false)
          return
        }
        if (!currentOpenid) {
          currentOpenid = await ensureWechatOpenid(token)
          if (!currentOpenid) {
            // 已跳转 OAuth 授权（页面即将刷新）
            setIsLoading(false)
            return
          }
          setUserOpenid(currentOpenid)
        }
      }

      const res: any = await paymentApi.createWechatOrder({
        points: effectivePoints,
        pay_type: payType as 'jsapi' | 'native' | 'h5',
        openid: payType === 'jsapi' ? currentOpenid || undefined : undefined,
      })
      const orderId: number | undefined = res.data?.order_id

      if (payType === 'jsapi' && res.data?.pay_params) {
        await wxChooseWXPay(res.data.pay_params)
        if (orderId) {
          const success = await pollOrderStatus(orderId)
          if (success) {
            finishRecharge()
            return
          }
        }
        alert('支付结果确认超时，如已支付请稍后查看积分明细')
        setIsLoading(false)
        return
      } else if (payType === 'h5' && res.data?.h5_url) {
        // H5 支付：直接跳转到微信收银台
        window.location.href = res.data.h5_url
        if (orderId) startPolling(orderId)
        return
      } else if (payType === 'native' && res.data?.code_url) {
        setQrCodeUrl(res.data.code_url)
        setIsLoading(false)
        if (orderId) startPolling(orderId)
        return
      }

      throw new Error('获取支付参数失败')
    } catch (err: any) {
      console.error('[RechargePage] 充值失败:', err)
      alert(`充值失败: ${err?.response?.data?.detail || err?.message || String(err)}`)
      setIsLoading(false)
    }
  }

  const startPolling = (orderId: number) => {
    let count = 0
    const maxCount = 150 // 轮询5分钟（每2秒一次）
    let timedOut = false
    const timer = setInterval(async () => {
      count++
      try {
        const res: any = await paymentApi.getOrderStatus(orderId)
        if (res.data?.status === 'paid') {
          clearInterval(timer)
          setQrCodeUrl(null)
          setQrExpired(false)
          finishRecharge()
          return
        }
      } catch (e) {
        console.warn('查询订单状态失败:', e)
      }
      if (count >= maxCount && !timedOut) {
        timedOut = true
        clearInterval(timer)
        setQrExpired(true)
      }
    }, 2000)
  }

  const finishRecharge = async () => {
    await fetchUserInfo()
    addTransaction('recharge', effectivePoints, `充值${effectivePoints}积分 - 微信支付`)
    setIsLoading(false)
    setQrCodeUrl(null)
    setShowSuccess(true)
  }

  const pollOrderStatus = (orderId: number): Promise<boolean> => {
    return new Promise((resolve) => {
      let count = 0
      const maxCount = 10
      const timer = setInterval(async () => {
        count++
        try {
          const res: any = await paymentApi.getOrderStatus(orderId)
          if (res.data?.status === 'paid') {
            clearInterval(timer)
            resolve(true)
            return
          }
        } catch (e) {
          console.warn('查询订单状态失败:', e)
        }
        if (count >= maxCount) {
          clearInterval(timer)
          resolve(false)
        }
      }, 2000)
    })
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 relative">
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
        <h1 className="text-lg font-bold text-gray-800">购买积分</h1>
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

      {/* 充值档位 */}
      <div className="mb-4">
        <h3 className="text-gray-700 font-medium mb-3 text-sm">充值金额</h3>
        <div className="grid grid-cols-3 gap-3">
          {rechargeOptions.map((option) => (
            <button
              key={option.points}
              onClick={() => handleSelectPreset(option.points)}
              className={`py-3 rounded-xl border-2 transition-all ${
                !isCustomMode && selectedPoints === option.points
                  ? 'border-primary-600 bg-primary-50 text-primary-700'
                  : 'border-gray-200 text-gray-600 hover:border-gray-300'
              }`}
            >
              <div className="text-lg font-bold">{option.points}积分</div>
              <div className="text-xs text-gray-500">¥{option.amount}</div>
            </button>
          ))}
        </div>

        {/* 自定义按钮 + 展开输入框 */}
        <div className="mt-3">
          <button
            onClick={() => setIsCustomMode(true)}
            className={`w-full py-3 rounded-xl border-2 transition-all ${
              isCustomMode
                ? 'border-primary-600 bg-primary-50 text-primary-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <div className="text-sm font-medium">自定义积分</div>
          </button>
          {isCustomMode && (
            <div className="mt-2">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="numeric"
                  value={customPoints}
                  onChange={(e) => handleCustomInput(e.target.value)}
                  placeholder={`输入 ${MIN_POINTS}~${MAX_POINTS} 之间的整数`}
                  className="flex-1 px-4 py-3 rounded-xl border-2 border-primary-600 bg-primary-50 text-sm outline-none transition-all"
                  style={{ color: '#44403d' }}
                  autoFocus
                />
                <span className="text-sm text-gray-500 whitespace-nowrap">积分</span>
              </div>
              {customPoints && !isCustomValid && (
                <p className="mt-1.5 text-xs" style={{ color: '#a86c50' }}>请输入 {MIN_POINTS}~{MAX_POINTS} 之间的整数</p>
              )}
              {isCustomValid && (
                <p className="mt-1.5 text-xs text-gray-500">¥{(customPointsNum / 10).toFixed(1)}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 支付方式 - 固定微信支付 */}
      <div className="mb-4">
        <h3 className="text-gray-700 font-medium mb-3 text-sm">支付方式</h3>
        <div className="w-full py-3 px-4 rounded-xl border-2 border-green-500 bg-green-50 flex items-center justify-between">
          <div className="flex items-center">
            <svg width="20" height="20" viewBox="0 0 24 24" className="mr-3" fill="#07c160">
              <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.328.328 0 0 0 .176-.054l1.826-1.064a.858.858 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.81-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.802-.608-3.499-4.313-6.446-8.842-6.446zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 4.388c-3.84 0-6.96 2.59-6.96 5.785 0 3.196 3.12 5.786 6.96 5.786.81 0 1.59-.11 2.33-.301a.7.7 0 0 1 .583.08l1.492.863a.27.27 0 0 0 .143.043c.131 0 .237-.107.237-.24 0-.058-.024-.116-.039-.174l-.318-1.197a.482.482 0 0 1 .174-.548C23.284 19.338 24.42 17.63 24.42 15.7c0-3.196-3.12-5.786-6.96-5.786zm-2.882 4.414c.523 0 .946.43.946.96a.953.953 0 0 1-.946.96.953.953 0 0 1-.946-.96c0-.53.423-.96.946-.96zm5.763 0c.523 0 .946.43.946.96a.953.953 0 0 1-.946.96.953.953 0 0 1-.946-.96c0-.53.423-.96.946-.96z"/>
            </svg>
            <span className="text-gray-700 font-medium text-sm">微信支付</span>
          </div>
          <span className="text-green-500">✓</span>
        </div>
      </div>

      {/* 充值按钮 */}
      <div className="pb-3">
        <button
          onClick={handleRecharge}
          disabled={isLoading || effectivePoints === 0 || qrCodeUrl !== null}
          className="w-full py-3.5 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
        >
          {isLoading ? '处理中...' : qrCodeUrl ? '请使用微信扫码支付' : effectivePoints > 0 ? `充值 ${effectivePoints} 积分 (¥${(effectivePoints / 10).toFixed(1)})` : '请选择或输入积分'}
        </button>
        <div className="mt-2 text-center text-gray-400 text-xs">1元 = 10积分（自定义范围 {MIN_POINTS}~{MAX_POINTS}）</div>
      </div>

      {/* Native 支付二维码 */}
      {qrCodeUrl && !qrExpired && (
        <div className="mt-4 p-6 rounded-xl text-center" style={{ backgroundColor: '#eceae6' }}>
          <h3 className="text-gray-700 font-medium mb-4 text-base">请使用微信扫码支付</h3>
          <div className="flex justify-center mb-4">
            <canvas ref={qrCanvasRef} className="rounded-lg" style={{ backgroundColor: '#fff', padding: '8px' }} />
          </div>
          <p className="text-sm text-gray-500 mb-2">支付金额：<span className="font-bold text-gray-700">¥{(effectivePoints / 10).toFixed(1)}</span></p>
          <p className="text-xs text-gray-400">支付完成后自动确认，请勿刷新页面</p>
          <button
            onClick={() => {
              setQrCodeUrl(null)
              setQrExpired(false)
            }}
            className="mt-4 px-4 py-2 rounded-lg text-sm transition-colors"
            style={{ backgroundColor: '#d8d4d0', color: '#615c59' }}
          >
            取消支付
          </button>
        </div>
      )}

      {/* 二维码过期提示 */}
      {qrExpired && (
        <div className="mt-4 p-6 rounded-xl text-center" style={{ backgroundColor: '#eceae6' }}>
          <div className="text-4xl mb-3">⏰</div>
          <p className="text-gray-600 text-sm mb-1">二维码已过期</p>
          <p className="text-gray-400 text-xs mb-4">请刷新二维码后重新扫码</p>
          <button
            onClick={() => {
              setQrCodeUrl(null)
              setQrExpired(false)
              handleRecharge()
            }}
            className="px-6 py-2 rounded-xl text-sm font-medium transition-all"
            style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
          >
            刷新二维码
          </button>
        </div>
      )}

      {/* 成功提示 */}
      {showSuccess && (
        <div className="absolute inset-0 bg-white/90 flex items-center justify-center rounded-t-3xl z-50">
          <div className="text-center">
            <div className="text-5xl mb-3">✅</div>
            <h3 className="text-lg font-bold text-gray-800 mb-1">充值成功</h3>
            <p className="text-gray-500 text-sm mb-4">积分已到账</p>
            <button
              onClick={() => setShowSuccess(false)}
              className="px-6 py-2 rounded-xl text-sm font-medium transition-all"
              style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
            >
              知道了
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
