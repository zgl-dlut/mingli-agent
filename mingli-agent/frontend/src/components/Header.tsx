import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useUserStore } from '../store/userStore'
import { usePersonStore } from '../store/personStore'
import { isApp } from '../utils/platform'
import ShareModal from './ShareModal'

interface HeaderProps {
  onToggleHistory?: () => void
  isDesktop?: boolean
  isHistoryOpen?: boolean
}

export default function Header({ onToggleHistory, isDesktop = false, isHistoryOpen = false }: HeaderProps) {
  const { user, isLoggedIn } = useUserStore()
  const { persons } = usePersonStore()
  const location = useLocation()
  const [showShare, setShowShare] = useState(false)

  // 命盘入口指向默认（第一个）档案；无档案时回落到首页去创建
  // 今日 / 命盘为 App 端专属功能，浏览器直开（H5/PC）不展示入口
  const chartPath = persons.length > 0 ? `/chart/${persons[0].id}` : '/'
  const navItems = isApp()
    ? [
        { to: '/today', label: '今日', active: location.pathname === '/today' },
        { to: chartPath, label: '命盘', active: location.pathname.startsWith('/chart') },
      ]
    : []

  return (
    <header style={{ backgroundColor: '#8b6f5a', height: '64px', padding: '0 12px' }} className="flex items-center justify-between sticky top-0 z-40">
      {/* 左侧：按钮 + 品牌名 */}
      <div className="flex items-center gap-2">
        {/* 展开按钮 - 仅桌面端且面板收起时显示 */}
        {onToggleHistory && isDesktop && !isHistoryOpen && (
          <button
            onClick={onToggleHistory}
            className="rounded-lg transition-all hover:opacity-[0.85] flex items-center justify-center"
            style={{ color: '#f4f2f0', width: '32px', height: '32px' }}
            title="展开分析历史"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        )}
        {/* 移动端菜单按钮 */}
        {onToggleHistory && !isDesktop && (
          <button
            onClick={onToggleHistory}
            className="rounded-lg transition-all hover:opacity-[0.85] flex items-center justify-center"
            style={{ color: '#f4f2f0', width: '32px', height: '32px', fontSize: '18px' }}
          >
            ☰
          </button>
        )}
        <span className="logo-text" style={{ lineHeight: '32px', letterSpacing: '0' }}>趣算算</span>
        {/* 今日 / 命盘 切换（App 端专属） */}
        {navItems.length > 0 && (
          <nav className="flex items-center gap-1 ml-1">
            {navItems.map((item) => (
              <Link
                key={item.label}
                to={item.to}
                style={{
                  color: item.active ? '#f4f2f0' : 'rgba(244,242,240,0.65)',
                  fontSize: '13px',
                  padding: '4px 8px',
                  borderRadius: '999px',
                  backgroundColor: item.active ? 'rgba(244,242,240,0.18)' : 'transparent',
                  textDecoration: 'none',
                }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}
      </div>

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
