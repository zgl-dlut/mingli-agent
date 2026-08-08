import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { useUserStore } from './store/userStore'
import Layout from './components/Layout'
import AddPerson from './pages/AddPerson'
import Chat from './pages/Chat'
import LoginPage from './pages/LoginPage'
import LegalPage from './pages/LegalPage'
import FeedbackDashboard from './pages/FeedbackDashboard'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isLoggedIn = useUserStore((s) => s.isLoggedIn)
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/legal/terms',
    element: <LegalPage type="terms" />,
  },
  {
    path: '/legal/privacy',
    element: <LegalPage type="privacy" />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <Layout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <AddPerson /> },
      { path: 'chat/:personId', element: <Chat /> },
      { path: 'feedback', element: <FeedbackDashboard /> },
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}
