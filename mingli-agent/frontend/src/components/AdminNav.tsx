import { Link, useLocation } from 'react-router-dom'
import Logo from './Logo'

const tabs = [
  { path: '/feedback', label: '反馈看板' },
  { path: '/admin/usage', label: '用量记录' },
  { path: '/admin/orders', label: '订单记录' },
  { path: '/admin/recharge', label: '积分充值' },
  { path: '/admin/eval', label: '评测中心' },
  { path: '/admin/prompt-review', label: '人工审核' },
  { path: '/admin/prompt-versions', label: 'Prompt 版本' },
]

export default function AdminNav() {
  const { pathname } = useLocation()
  return (
    <div className="bg-white border-b border-slate-200 px-4 md:px-6 flex items-center gap-3">
      <Logo dark className="logo-sm" showText={false} />
      <div className="flex gap-1">
        {tabs.map((t) => (
          <Link
            key={t.path}
            to={t.path}
            className={`px-4 py-2.5 text-sm border-b-2 transition-colors ${
              pathname === t.path
                ? 'border-blue-500 text-blue-600 font-medium'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t.label}
          </Link>
        ))}
      </div>
    </div>
  )
}
