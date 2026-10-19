import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Header from './Header'
import TabBar from './TabBar'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'

/**
 * 全局布局
 * 用户区：完全 App 形态——内容锁定在居中的手机宽度容器内（宽屏两侧留白），
 *         容器内独立滚动，底部常驻 Tab 栏（今日/对话/我的），不出现 PC 浏览器排版。
 * 管理后台（/admin）：数据表格场景，保留全宽排版且不显示 Tab 栏。
 */
export default function Layout() {
  const location = useLocation()
  const { fetchPersons } = usePersonStore()
  const { fetchUserInfo } = useUserStore()

  const isAdminArea = location.pathname.startsWith('/admin')

  useEffect(() => {
    fetchPersons()
    fetchUserInfo()
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
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('focus', handleFocus)
    }
  }, [])

  return (
    <div
      className="h-screen overflow-hidden"
      style={{ height: '100dvh', backgroundColor: isAdminArea ? '#f2f0ed' : '#dfdcd8' }}
    >
      {/* App 容器：用户区锁定手机宽度居中；管理后台全宽 */}
      <div
        className="relative mx-auto h-full flex flex-col overflow-hidden"
        style={isAdminArea ? {} : { maxWidth: '430px', backgroundColor: '#f2f0ed', boxShadow: '0 0 24px rgba(0,0,0,0.10)' }}
      >
        {/* 通用Header - 常驻容器顶部 */}
        <Header />

        {/* 页面内容：容器内独立滚动 */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>

        {/* 底部常驻 Tab 栏（用户区） */}
        {!isAdminArea && <TabBar />}
      </div>
    </div>
  )
}
