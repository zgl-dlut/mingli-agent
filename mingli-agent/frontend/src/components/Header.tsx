import { useState } from 'react'
import { useUserStore } from '../store/userStore'
import ShareModal from './ShareModal'
import { color } from '../theme/tokens'

/**
 * 通用顶栏 —— 对齐设计稿：素底（页面底色）+ 墨色文字，无彩色填充。
 * 设计稿各页顶栏均为 `.navbar`（16px 内边距 + 17px 加粗标题）/ 页面自有 topbar。
 */
export default function Header() {
  const { user, isLoggedIn } = useUserStore()
  const [showShare, setShowShare] = useState(false)

  return (
    <header
      className="flex items-center justify-between flex-none"
      style={{ backgroundColor: color.bg, height: '56px', padding: '0 16px' }}
    >
      {/* 左侧：品牌名（设计稿 navbar.title 规格） */}
      <span style={{ fontSize: '17px', fontWeight: 700, color: color.ink }}>趣算算</span>

      {/* 右侧：分享赚积分 + 积分 */}
      <div className="flex items-center gap-2">
        {isLoggedIn && (
          <button
            onClick={() => setShowShare(true)}
            className="rounded-full flex items-center gap-1 transition-all active:scale-95"
            style={{ backgroundColor: color.brandSoft, padding: '5px 10px', color: color.brand, fontSize: '12px', fontWeight: 600 }}
          >
            <span style={{ fontSize: '11px' }}>🎁</span>
            <span>分享得积分</span>
          </button>
        )}
        <div className="rounded-full flex items-center" style={{ backgroundColor: color.card, padding: '5px 10px', border: '1px solid #E4E1DA' }}>
          <span style={{ color: color.gold, fontSize: '12px', marginRight: '3px' }}>⭐</span>
          <span style={{ color: color.ink, fontSize: '13px', fontWeight: 600 }}>{user?.points ?? 0}</span>
        </div>
      </div>

      {showShare && <ShareModal onClose={() => setShowShare(false)} />}
    </header>
  )
}
