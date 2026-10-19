import { useLocation, useNavigate } from 'react-router-dom'
import { usePersonStore } from '../store/personStore'
import { useChatStore } from '../store/chatStore'

/**
 * 底部常驻 Tab 栏（设计稿 00-index 主导航）：今日 / 对话 / 我的
 * 纯 App 形态，仅在用户区渲染（admin 后台不渲染，由 Layout 控制）。
 */

interface TabItem {
  key: string
  label: string
  icon: JSX.Element
  isActive: (pathname: string) => boolean
}

const TABS: TabItem[] = [
  {
    key: 'today',
    label: '今日',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="12" r="4.2" />
        <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.5 1.5M17.2 17.2l1.5 1.5M18.7 5.3l-1.5 1.5M6.8 17.2l-1.5 1.5" />
      </svg>
    ),
    isActive: (p) => p === '/today',
  },
  {
    key: 'chat',
    label: '对话',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5.6L3 21.2V11.5A7.5 7.5 0 0 1 10.5 4h2A7.5 7.5 0 0 1 20 11.5z" />
      </svg>
    ),
    isActive: (p) => p.startsWith('/chat'),
  },
  {
    key: 'profile',
    label: '我的',
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="12" cy="8" r="3.8" />
        <path d="M4.5 20.5c1.2-3.4 4-5 7.5-5s6.3 1.6 7.5 5" />
      </svg>
    ),
    isActive: (p) => p === '/profile' || p === '/persons',
  },
]

export default function TabBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { persons } = usePersonStore()
  const { currentPersonId } = useChatStore()

  const handleTabPress = (key: string) => {
    if (key === 'today') {
      navigate('/today')
      return
    }
    if (key === 'chat') {
      // 优先回到当前会话，其次第一个档案；无档案则去首页建档
      const targetId = currentPersonId ?? persons[0]?.id
      navigate(targetId ? `/chat/${targetId}` : '/')
      return
    }
    navigate('/profile')
  }

  return (
    <nav
      className="flex-none flex"
      style={{
        backgroundColor: '#FFFFFF',
        borderTop: '1px solid #ECEAE4',
        padding: '7px 0 max(10px, env(safe-area-inset-bottom))',
      }}
    >
      {TABS.map((tab) => {
        const active = tab.isActive(location.pathname)
        return (
          <button
            key={tab.key}
            onClick={() => handleTabPress(tab.key)}
            className="flex-1 flex flex-col items-center gap-0.5 bg-transparent border-0"
            style={{
              fontSize: '10px',
              color: active ? '#8b6f5a' : '#9B958B',
              fontWeight: active ? 600 : 400,
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
