import { useState, useEffect } from 'react'
import { authApi } from '../api/auth'

interface ShareModalProps {
  onClose: () => void
}

/**
 * 分享赚积分弹窗：展示专属邀请链接 + 复制按钮 + 活动说明
 * 好友通过链接注册后，后端自动给邀请人发放 80 积分（biz_type=share_reward）
 * 链接使用不可猜测的邀请码（?ref=Xk9mP2vQ），非明文用户ID
 */
export default function ShareModal({ onClose }: ShareModalProps) {
  const [copied, setCopied] = useState(false)
  const [inviteCode, setInviteCode] = useState<string>('')

  useEffect(() => {
    authApi.getInviteCode()
      .then(({ data }) => setInviteCode(data.invite_code || ''))
      .catch((e) => console.error('获取邀请码失败:', e))
  }, [])

  const shareLink = inviteCode ? `https://www.qusuansuan.com/?ref=${inviteCode}` : '生成中...'

  const handleCopy = async () => {
    // navigator.clipboard 在部分微信内置浏览器不可用，降级 textarea + execCommand
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(shareLink)
      } else {
        const ta = document.createElement('textarea')
        ta.value = shareLink
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (e) {
      console.error('复制失败:', e)
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
          <h2 className="text-lg font-bold text-gray-800">🎁 分享得积分</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <div className="px-5 pb-5">
          {/* 主视觉文案 */}
          <div className="rounded-xl p-4 mb-4 text-center" style={{ backgroundColor: '#faf6ef' }}>
            <div className="text-2xl font-bold" style={{ color: '#a18072' }}>邀请 1 位好友 = 80 积分</div>
            <div className="text-xs text-gray-500 mt-1">好友注册成功，积分实时到账</div>
          </div>

          {/* 分享链接 */}
          <div className="mb-2 text-sm text-gray-700 font-medium">你的专属邀请链接</div>
          <div className="flex items-center gap-2 mb-4">
            <div
              className="flex-1 rounded-lg px-3 py-2.5 text-sm text-gray-600 truncate"
              style={{ backgroundColor: '#f4f2f0' }}
              title={shareLink}
            >
              {shareLink}
            </div>
            <button
              onClick={handleCopy}
              disabled={!inviteCode}
              className="flex-shrink-0 rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-all active:scale-95 disabled:opacity-50"
              style={{ backgroundColor: copied ? '#7a9a6d' : '#a18072' }}
            >
              {copied ? '已复制 ✓' : '复制链接'}
            </button>
          </div>

          {/* 活动说明 */}
          <div className="rounded-xl p-4" style={{ backgroundColor: '#eceae6' }}>
            <div className="text-sm font-medium text-gray-700 mb-2">活动说明</div>
            <ul className="text-xs text-gray-500 space-y-1.5 leading-relaxed">
              <li>· 好友通过你的链接注册，你立即获得 <span className="font-medium" style={{ color: '#a18072' }}>80 积分</span></li>
              <li>· 好友注册同时获得 240 新用户积分（1次报告+2次追问）</li>
              <li>· 积分实时到账，可在「积分明细」中查看</li>
              <li>· 邀请人数不限，多邀多得</li>
            </ul>
          </div>

          {/* 底部关闭按钮 */}
          <button
            onClick={onClose}
            className="w-full mt-4 rounded-lg py-3 text-sm font-medium text-white transition-all active:scale-[0.98]"
            style={{ backgroundColor: '#a18072' }}
          >
            知道了
          </button>
        </div>
      </div>
    </div>
  )
}
