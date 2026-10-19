import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUserStore } from '../store/userStore'
import { authApi } from '../api/auth'
import ShareModal from '../components/ShareModal'
import ContactModal from '../components/ContactModal'

/**
 * 我的页（设计稿 04-profile）
 * 用户卡 + 积分卡 + 功能列表；账号类操作（改昵称/注销/退出）集中在此。
 */
export default function ProfilePage() {
  const navigate = useNavigate()
  const { user, logout, setUser, sendSmsCode } = useUserStore()

  const [showShare, setShowShare] = useState(false)
  const [showContact, setShowContact] = useState(false)
  const [showNicknameModal, setShowNicknameModal] = useState(false)
  const [nickname, setNickname] = useState('')
  const [savingNickname, setSavingNickname] = useState(false)
  const [showDeleteAccount, setShowDeleteAccount] = useState(false)
  const [deleteCode, setDeleteCode] = useState('')
  const [smsCountdown, setSmsCountdown] = useState(0)
  const [smsSending, setSmsSending] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const isMobileAccount = !!user?.phone

  const handleOpenNicknameModal = () => {
    setNickname(user?.name || '')
    setShowNicknameModal(true)
  }

  const handleSaveNickname = async () => {
    const name = nickname.trim()
    if (!name) return
    setSavingNickname(true)
    try {
      const { data } = await authApi.updateProfile(name)
      if (user) setUser({ ...user, name: data.name })
      setShowNicknameModal(false)
    } catch (err: any) {
      alert(err?.response?.data?.detail || '昵称修改失败')
    } finally {
      setSavingNickname(false)
    }
  }

  const handleOpenDeleteModal = () => {
    setDeleteCode('')
    setSmsCountdown(0)
    setShowDeleteAccount(true)
  }

  const handleSendDeleteSms = async () => {
    if (!user?.phone || smsSending || smsCountdown > 0) return
    setSmsSending(true)
    try {
      const res = await sendSmsCode(user.phone)
      // 开发模式后端直接回传验证码，自动填入方便测试
      if (res?.dev_mode && res.code) setDeleteCode(res.code)
      setSmsCountdown(60)
      const timer = setInterval(() => {
        setSmsCountdown((c) => {
          if (c <= 1) {
            clearInterval(timer)
            return 0
          }
          return c - 1
        })
      }, 1000)
    } catch (err: any) {
      alert(err?.response?.data?.detail || '验证码发送失败')
    } finally {
      setSmsSending(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (deleting) return
    if (isMobileAccount && !deleteCode.trim()) {
      alert('请输入短信验证码')
      return
    }
    if (!window.confirm('最后确认：注销后所有人物档案与对话将永久删除，确定继续吗？')) return
    setDeleting(true)
    try {
      await authApi.deleteAccount(isMobileAccount ? deleteCode.trim() : null)
      setShowDeleteAccount(false)
      logout()
      navigate('/login', { replace: true })
      alert('账号已注销，您的个人数据已删除')
    } catch (err: any) {
      alert(err?.response?.data?.detail || '注销失败，请稍后重试')
    } finally {
      setDeleting(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="px-4 py-4 pb-6" style={{ maxWidth: '430px', margin: '0 auto' }}>
      {/* 用户卡 */}
      <div className="bg-white rounded-2xl p-4 shadow-sm flex items-center gap-3">
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center text-white text-lg font-bold flex-none"
          style={{ backgroundColor: '#8b6f5a' }}
        >
          {user?.name?.[0] || '?'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-base font-semibold text-gray-800 truncate">{user?.name || '未设置昵称'}</div>
          <div className="text-xs text-gray-400 mt-0.5">{user?.phone || ''}</div>
        </div>
        <button onClick={handleOpenNicknameModal} className="text-xs flex-none" style={{ color: '#8b6f5a' }}>
          编辑 ›
        </button>
      </div>

      {/* 积分卡 */}
      <div className="bg-white rounded-2xl p-4 shadow-sm mt-3">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">积分余额</span>
          <button
            onClick={() => navigate('/recharge')}
            className="text-xs rounded-full px-3 py-1 text-white"
            style={{ backgroundColor: '#a7876f' }}
          >
            充值
          </button>
        </div>
        <div className="mt-1">
          <span className="text-3xl font-bold" style={{ color: '#8b6f5a' }}>{user?.points ?? 0}</span>
          <span className="text-xs text-gray-400 ml-1">分</span>
        </div>
        <div className="flex items-center gap-4 mt-2">
          <button onClick={() => setShowShare(true)} className="text-xs flex items-center gap-0.5" style={{ color: '#C9A86A' }}>
            邀请赚积分 <span>›</span>
          </button>
          <button onClick={() => navigate('/points')} className="text-xs flex items-center gap-0.5 text-gray-500">
            消费记录 <span>›</span>
          </button>
        </div>
      </div>

      {/* 功能列表 */}
      <div className="bg-white rounded-2xl shadow-sm mt-3 divide-y divide-gray-50">
        <button onClick={() => navigate('/persons')} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>我的档案</span>
          <span className="text-gray-300">›</span>
        </button>
        <button onClick={() => setShowShare(true)} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>邀请好友</span>
          <span className="text-gray-300">›</span>
        </button>
        <button onClick={() => navigate('/feedback')} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>帮助与反馈</span>
          <span className="text-gray-300">›</span>
        </button>
        <button onClick={() => setShowContact(true)} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>联系我们</span>
          <span className="text-gray-300">›</span>
        </button>
        <button onClick={() => navigate('/legal/terms')} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>用户服务协议</span>
          <span className="text-gray-300">›</span>
        </button>
        <button onClick={() => navigate('/legal/privacy')} className="w-full flex items-center justify-between px-4 py-3.5 text-sm text-gray-800">
          <span>隐私政策</span>
          <span className="text-gray-300">›</span>
        </button>
      </div>

      {/* 账号操作 */}
      <div className="bg-white rounded-2xl shadow-sm mt-3 divide-y divide-gray-50">
        <button onClick={handleOpenDeleteModal} className="w-full px-4 py-3.5 text-sm text-left" style={{ color: '#D9534F' }}>
          注销账号
        </button>
        <button onClick={handleLogout} className="w-full px-4 py-3.5 text-sm text-left" style={{ color: '#D9534F' }}>
          退出登录
        </button>
      </div>

      {showShare && <ShareModal onClose={() => setShowShare(false)} />}
      {showContact && <ContactModal onClose={() => setShowContact(false)} />}

      {/* 修改昵称弹窗 */}
      {showNicknameModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30" onClick={() => setShowNicknameModal(false)}>
          <div className="w-full max-w-md bg-white rounded-2xl p-5 shadow-xl mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-gray-800 text-base font-medium mb-4">修改昵称</h3>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveNickname() }}
              maxLength={20}
              placeholder="请输入昵称（1-20 个字符）"
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 mb-4"
              autoFocus
            />
            <div className="flex gap-3">
              <button onClick={() => setShowNicknameModal(false)} className="flex-1 py-2.5 rounded-lg border border-gray-200 text-gray-600 text-sm">
                取消
              </button>
              <button
                onClick={handleSaveNickname}
                disabled={savingNickname || !nickname.trim()}
                className="flex-1 py-2.5 rounded-lg text-white text-sm disabled:opacity-40"
                style={{ backgroundColor: '#a7876f' }}
              >
                {savingNickname ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 注销账号弹窗 */}
      {showDeleteAccount && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30" onClick={() => setShowDeleteAccount(false)}>
          <div className="w-full max-w-md bg-white rounded-2xl p-5 shadow-xl mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-gray-800 text-base font-medium mb-2">注销账号</h3>
            <p className="text-gray-500 text-sm mb-4">注销后所有人物档案与对话将永久删除，且无法恢复。</p>
            {isMobileAccount && (
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  maxLength={6}
                  value={deleteCode}
                  onChange={(e) => setDeleteCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="短信验证码"
                  className="flex-1 min-w-0 px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <button
                  onClick={handleSendDeleteSms}
                  disabled={smsSending || smsCountdown > 0}
                  className="px-3 py-2.5 rounded-lg text-xs whitespace-nowrap disabled:opacity-40"
                  style={{ backgroundColor: '#F5F0E8', color: '#8B6F5A' }}
                >
                  {smsCountdown > 0 ? `${smsCountdown}s` : '获取验证码'}
                </button>
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={() => setShowDeleteAccount(false)} className="flex-1 py-2.5 rounded-lg border border-gray-200 text-gray-600 text-sm">
                取消
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={deleting}
                className="flex-1 py-2.5 rounded-lg bg-red-500 text-white text-sm disabled:opacity-40"
              >
                {deleting ? '注销中…' : '确认注销'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
