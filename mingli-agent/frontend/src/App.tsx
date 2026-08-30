import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { useEffect } from 'react'
import { useUserStore } from './store/userStore'
import Layout from './components/Layout'
import AddPerson from './pages/AddPerson'
import Chat from './pages/Chat'
import LoginPage from './pages/LoginPage'
import LegalPage from './pages/LegalPage'
import FeedbackDashboard from './pages/FeedbackDashboard'
import PointsHistoryPage from './pages/PointsHistoryPage'
import RechargePage from './pages/RechargePage'
import UsageDashboard from './pages/UsageDashboard'
import OrdersDashboard from './pages/OrdersDashboard'
import EvalDashboard from './pages/EvalDashboard'
import EvalDashboardTest from './pages/EvalDashboardTest'
import EvalComparePage from './pages/EvalComparePage'
import EvalDetailPage from './pages/EvalDetailPage'
import PromptReviewPage from './pages/PromptReviewPage'
import PromptVersionPage from './pages/PromptVersionPage'
import AdminRechargePage from './pages/AdminRechargePage'
import AdminLoginPage from './pages/AdminLoginPage'

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
      { path: 'orders', element: <OrdersDashboard /> },
      { path: 'eval', element: <EvalDashboard /> },
      { path: 'eval-test', element: <EvalDashboardTest /> },
      { path: 'eval-detail/:id', element: <EvalDetailPage /> },
      { path: 'eval-compare', element: <EvalComparePage /> },
      { path: 'prompt-review', element: <PromptReviewPage /> },
      { path: 'prompt-versions', element: <PromptVersionPage /> },
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
      { path: 'chat/:personId', element: <Chat /> },
      { path: 'points', element: <PointsHistoryPage /> },
      { path: 'recharge', element: <RechargePage /> },
      { path: 'feedback', element: <FeedbackDashboard /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
