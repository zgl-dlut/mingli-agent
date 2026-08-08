import { useUserStore } from '../store/userStore'

interface HeaderProps {
  onToggleHistory?: () => void
  isDesktop?: boolean
  isHistoryOpen?: boolean
}

export default function Header({ onToggleHistory, isDesktop = false, isHistoryOpen = false }: HeaderProps) {
  const { user } = useUserStore()
  
  return (
    <header className="bg-gradient-to-r from-primary-600 to-primary-800 px-4 py-3 sticky top-0 z-40">
      <div className="flex items-center justify-between">
        {/* 左侧：按钮 + 品牌logo + 品牌名 */}
        <div className="flex items-center gap-2">
          {/* 展开按钮 - 仅桌面端且面板收起时显示 */}
          {onToggleHistory && isDesktop && !isHistoryOpen && (
            <button
              onClick={onToggleHistory}
              className="text-white/80 hover:text-white w-8 h-8 flex items-center justify-center rounded-lg hover:bg-white/10 transition-all"
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
              className="text-white/80 hover:text-white text-xl w-10 h-10 flex items-center justify-center rounded-lg hover:bg-white/10 transition-all"
            >
              ☰
            </button>
          )}
          <span className="text-lg font-bold text-white">趣算算</span>
        </div>
        
        {/* 右侧：积分 */}
        <div className="flex items-center gap-2">
          <div className="bg-white/20 backdrop-blur-sm rounded-full px-3 py-1.5 flex items-center">
            <span className="text-yellow-300 text-sm mr-1">⭐</span>
            <span className="text-white text-sm font-medium">{user?.points ?? 0}</span>
          </div>
        </div>
      </div>
    </header>
  )
}
