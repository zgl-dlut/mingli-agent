import { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header'
import HistoryPanel from './HistoryPanel'
import { useNavigate } from 'react-router-dom'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { fetchPersons } = usePersonStore()
  const { fetchUserInfo } = useUserStore()

  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [isDesktop, setIsDesktop] = useState(false)

  useEffect(() => {
    fetchPersons()
    fetchUserInfo()
    const checkDesktop = () => {
      setIsDesktop(window.innerWidth >= 768)
    }
    checkDesktop()
    window.addEventListener('resize', checkDesktop)
    // 页面重新可见或获得焦点时同步后端数据（处理后端直接删除等场景）
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchPersons()
        fetchUserInfo()
      }
    }
    const handleFocus = () => {
      fetchPersons()
      fetchUserInfo()
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('focus', handleFocus)
    return () => {
      window.removeEventListener('resize', checkDesktop)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
    }
  }, [])
  
  const handleToggleHistory = () => {
    setIsHistoryOpen(!isHistoryOpen)
  }
  
  const handleNavigateToChat = (personId: number) => {
    navigate(`/chat/${personId}`)
  }
  
  const handleNavigateToAddPerson = () => {
    navigate('/', { replace: true, state: { timestamp: Date.now() } })
    window.location.reload()
  }
  
  const handleCloseHistory = () => {
    setIsHistoryOpen(false)
  }
  
  return (
    <div className={`min-h-screen ${isDesktop ? 'flex flex-col' : ''}`} style={{ backgroundColor: '#f2f0ed' }}>
      {/* 通用Header - 固定在顶部 */}
      <Header 
        onToggleHistory={handleToggleHistory}
        isDesktop={isDesktop}
        isHistoryOpen={isHistoryOpen}
      />
      
      {/* 主内容区域 */}
      <div className={`flex-1 flex ${isDesktop ? '' : 'block'}`}>
        {/* 桌面端：左侧历史面板 - 始终渲染，通过isOpen控制显示/隐藏 */}
        {isDesktop && location.pathname !== '/login' && (
          <HistoryPanel
            isOpen={isHistoryOpen}
            onClose={handleCloseHistory}
            onNavigateToChat={handleNavigateToChat}
            onNavigateToAddPerson={handleNavigateToAddPerson}
            isDesktop={true}
          />
        )}
        
        {/* 页面内容 */}
        <main className="flex-1 min-h-[calc(100vh-60px)]">
          <Outlet />
        </main>
        
        {/* 移动端历史面板 */}
        {!isDesktop && location.pathname !== '/login' && (
          <HistoryPanel
            isOpen={isHistoryOpen}
            onClose={() => setIsHistoryOpen(false)}
            onNavigateToChat={handleNavigateToChat}
            onNavigateToAddPerson={handleNavigateToAddPerson}
          />
        )}
      </div>
    </div>
  )
}
