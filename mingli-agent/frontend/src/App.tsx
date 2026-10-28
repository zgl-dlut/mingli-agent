import { createBrowserRouter, Navigate, RouterProvider, useParams } from 'react-router-dom'
import { useEffect } from 'react'
import { useUserStore } from './store/userStore'
import Layout from './components/Layout'
import AddPerson from './pages/AddPerson'
import Today from './pages/Today'
import Chart from './pages/Chart'
import DeepReading from './pages/DeepReading'
import ProfilePage from './pages/ProfilePage'
import PersonsPage from './pages/PersonsPage'
import LoginPage from './pages/LoginPage'
import LegalPage from './pages/LegalPage'
import FeedbackDashboard from './pages/FeedbackDashboard'
import PointsHistoryPage from './pages/PointsHistoryPage'
import UsageDashboard from './pages/UsageDashboard'
import OrdersDashboard from './pages/OrdersDashboard'
import EvalDashboard from './pages/EvalDashboard'
import AdminRechargePage from './pages/AdminRechargePage'
import AdminUsersPage from './pages/AdminUsersPage'
import AdminLoginPage from './pages/AdminLoginPage'
import ReadingHome from './pages/ReadingHome'
import ReadingChat from './pages/ReadingChat'
import ReportLibrary from './pages/ReportLibrary'
import ReportDetail from './pages/ReportDetail'
import SubscriptionPage from './pages/SubscriptionPage'
import PersonaHome from './pages/PersonaHome'
import PersonaChat from './pages/PersonaChat'
import PersonaMemoryPage from './pages/PersonaMemoryPage'
import { isApp } from './utils/platform'

/**
 * 分享链接邀请参数捕获：/?ref=邀请码 → localStorage（登录注册时带给后端）
 * 邀请码为8位随机字母数字（不可猜测），兼容旧版纯数字用户ID链接。
 * 模块加载时立即执行，早于路由渲染——未登录用户会被重定向到 /login，
 * 不能放在组件 useEffect 里（Navigate 的跳转 effect 先于父组件 effect 执行）。
 * 采用末次触点归因：以后点的最新分享链接为准。
 */
;(function captureInviterRef() {
  try {
    const params = new URLSearchParams(window.location.search)
    const ref = (params.get('ref') || '').trim()
    // 邀请码：8位字母数字；兼容旧版纯数字ID（1-10位）
    if (/^[0-9A-Za-z]{4,12}$/.test(ref) || /^\d{1,10}$/.test(ref)) {
      if (ref !== '0') {
        localStorage.setItem('inviter_ref', ref)
        // 清掉 URL 上的 ref 参数，保持地址栏干净
        params.delete('ref')
        const query = params.toString()
        const cleanUrl = window.location.pathname + (query ? `?${query}` : '') + window.location.hash
        window.history.replaceState({}, '', cleanUrl)
      }
    }
  } catch {
    /* 隐私模式等场景静默失败 */
  }
})()

/** OAuth 回调处理器：从 URL 中提取 token 并登录 */
function OAuthCallbackHandler({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (token) {
      localStorage.setItem('mingli_token', token)
      window.history.replaceState({}, '', window.location.pathname)
      useUserStore.getState().fetchUserInfo().finally(() => {
        window.location.href = '/'
      })
    }
  }, [])
  return <>{children}</>
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useUserStore((s) => s.isLoggedIn)
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function AdminProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('mingli_token')
  const isAdmin = localStorage.getItem('mingli_admin')
  if (!token || !isAdmin) {
    return <Navigate to="/admin-login" replace />
  }
  return <>{children}</>
}

/** App 端专属路由：浏览器直开（H5/PC）时重定向回首页，不暴露页面 */
function AppOnlyRoute({ children }: { children: React.ReactNode }) {
  if (!isApp()) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

function LegacyChatRedirect() {
  const { personId } = useParams<{ personId: string }>()
  return <Navigate to={`/reading/chat/${personId || ''}`} replace />
}

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/admin-login',
    element: <AdminLoginPage />,
  },
  {
    path: '/legal/terms',
    element: <LegalPage type="terms" />,
  },
  {
    path: '/legal/privacy',
    element: <LegalPage type="privacy" />,
  },
  // admin 路由：独立于用户路由，使用 AdminProtectedRoute
  {
    path: '/admin',
    element: (
      <AdminProtectedRoute>
        <Layout />
      </AdminProtectedRoute>
    ),
    children: [
      { path: 'usage', element: <UsageDashboard /> },
      { path: 'users', element: <AdminUsersPage /> },
      { path: 'orders', element: <OrdersDashboard /> },
      { path: 'eval', element: <EvalDashboard /> },
      { path: 'recharge', element: <AdminRechargePage /> },
    ],
  },
  {
    path: '/',
    element: (
      <OAuthCallbackHandler>
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      </OAuthCallbackHandler>
    ),
    children: [
      { index: true, element: <AddPerson /> },
      { path: 'today', element: <AppOnlyRoute><Today /></AppOnlyRoute> },
      { path: 'chart/:personId', element: <AppOnlyRoute><Chart /></AppOnlyRoute> },
      { path: 'deep-reading/:messageId', element: <AppOnlyRoute><DeepReading /></AppOnlyRoute> },
      { path: 'reading', element: <ReadingHome /> },
      { path: 'reading/chat/:personId', element: <ReadingChat /> },
      { path: 'reading/reports', element: <ReportLibrary /> },
      { path: 'reading/reports/:reportId', element: <ReportDetail /> },
      { path: 'subscription', element: <SubscriptionPage /> },
      { path: 'persona', element: <PersonaHome /> },
      { path: 'persona/chat/:conversationId', element: <PersonaChat /> },
      { path: 'persona/:personaId/memory', element: <PersonaMemoryPage /> },
      { path: 'profile', element: <ProfilePage /> },
      { path: 'persons', element: <PersonsPage /> },
      { path: 'chat/:personId', element: <LegacyChatRedirect /> },
      { path: 'points', element: <PointsHistoryPage /> },
      { path: 'feedback', element: <FeedbackDashboard /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
