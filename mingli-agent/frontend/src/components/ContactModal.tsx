import { useState } from 'react'

interface ContactModalProps {
  onClose: () => void
}

const SUPPORT_EMAIL = 'support@qusuansuan.com'

async function copyText(text: string): Promise<boolean> {
  // navigator.clipboard 在部分微信内置浏览器不可用，降级 textarea + execCommand
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch (e) {
    console.error('复制失败:', e)
    return false
  }
}

/**
 * 联系我们弹窗：客服邮箱（一键复制）+ 企业微信客服二维码
 */
export default function ContactModal({ onClose }: ContactModalProps) {
  const [copied, setCopied] = useState(false)
  const [qrError, setQrError] = useState(false)

  const handleCopyEmail = async () => {
    const ok = await copyText(SUPPORT_EMAIL)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="recharge-modal-overlay" onClick={onClose}>
      <div className="recharge-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* 顶部拖拽条 */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>

        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 pb-3">
          <h2 className="text-lg font-bold text-gray-800">联系我们</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <div className="px-5 pb-5">
          {/* 客服邮箱 */}
          <div className="mb-2 text-sm text-gray-700 font-medium">客服邮箱</div>
          <div className="flex items-center gap-2 mb-5">
            <div
              className="flex-1 rounded-lg px-3 py-2.5 text-sm text-gray-600 truncate"
              style={{ backgroundColor: '#f4f2f0' }}
            >
              📧 {SUPPORT_EMAIL}
            </div>
            <button
              onClick={handleCopyEmail}
              className="flex-shrink-0 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-all active:scale-95"
              style={{ backgroundColor: copied ? '#7a9a6d' : '#a18072' }}
            >
              {copied ? '已复制 ✓' : '复制'}
            </button>
          </div>

          {/* 企业微信客服二维码 */}
          <div className="rounded-xl p-4 text-center" style={{ backgroundColor: '#faf6ef' }}>
            <div className="text-sm font-medium text-gray-700 mb-3">企业微信客服</div>
            <div className="flex justify-center mb-2">
              {qrError ? (
                <div
                  className="w-48 h-48 rounded-lg flex items-center justify-center text-center px-4 text-xs text-gray-400 leading-relaxed"
                  style={{ backgroundColor: '#fff', border: '1px solid #eceae6' }}
                >
                  客服二维码更新中
                  <br />
                  请先通过邮箱联系我们
                </div>
              ) : (
                <img
                  src="/contact-qr.png"
                  alt="企业微信客服二维码"
                  className="w-48 h-48 rounded-lg bg-white"
                  style={{ border: '1px solid #eceae6' }}
                  onError={() => setQrError(true)}
                />
              )}
            </div>
            <div className="text-xs text-gray-500">微信扫码添加客服，工作日 10:00-19:00 在线</div>
          </div>

          {/* 底部关闭按钮 */}
          <button
            onClick={onClose}
            className="w-full mt-4 rounded-lg py-3 text-sm font-medium text-white transition-all active:scale-[0.98]"
            style={{ backgroundColor: '#a18072' }}
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}
