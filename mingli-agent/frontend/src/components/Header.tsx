import { useState } from 'react'
import { useUserStore } from '../store/userStore'
import ShareModal from './ShareModal'

/**
 * 通用顶栏：品牌 + 分享/积分。主导航由底部 TabBar 承担（设计稿 00-index）。
 */
export default function Header() {
  const { user, isLoggedIn } = useUserStore()
  const [showShare, setShowShare] = useState(false)

  return (
    <header style={{ backgroundColor: '#8b6f5a', height: '64px', padding: '0 12px' }} className="flex items-center justify-between flex-none">
      {/* 左侧：品牌名 */}
      <span className="logo-text" style={{ lineHeight: '32px', letterSpacing: '0' }}>趣算算</span>

      {/* 右侧：分享赚积分 + 积分 */}
      <div className="flex items-center gap-2">
        {isLoggedIn && (
          <button
            onClick={() => setShowShare(true)}
            className="rounded-full flex items-center gap-1 transition-all active:scale-95 hover:opacity-90"
            style={{ backgroundColor: 'rgba(244,242,240,0.15)', padding: '5px 10px', color: '#f4f2f0', fontSize: '13px' }}
          >
            <span style={{ fontSize: '12px' }}>🎁</span>
            <span>分享得积分</span>
          </button>
        )}
        <div className="rounded-full flex items-center" style={{ backgroundColor: 'rgba(244,242,240,0.15)', padding: '5px 10px' }}>
          <span style={{ color: '#c9b99f', fontSize: '12px', marginRight: '3px' }}>⭐</span>
          <span style={{ color: '#f4f2f0', fontSize: '13px', fontWeight: 400 }}>{user?.points ?? 0}</span>
        </div>
      </div>

      {showShare && <ShareModal onClose={() => setShowShare(false)} />}
    </header>
  )
}
