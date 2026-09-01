import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'
import { useChatStore } from '../store/chatStore'
import { authApi } from '../api/auth'
import type { Person } from '../types'
import { genderToText } from '../utils/gender'

interface HistoryPanelProps {
  isOpen: boolean
  onClose: () => void
  onNavigateToChat: (personId: number) => void
  onNavigateToAddPerson: () => void
  isDesktop?: boolean
}

export default function HistoryPanel({ isOpen, onClose, onNavigateToChat, onNavigateToAddPerson, isDesktop = false }: HistoryPanelProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { persons, deletePerson, renamePerson } = usePersonStore()
  const { user, logout, setUser } = useUserStore()
  const { deletePersonChat } = useChatStore()
  const [isExiting, setIsExiting] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [expandedMenuId, setExpandedMenuId] = useState<number | null>(null)
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [showNicknameModal, setShowNicknameModal] = useState(false)
  const [nickname, setNickname] = useState('')
  const [savingNickname, setSavingNickname] = useState(false)

  const handleClose = () => {
    setIsExiting(true)
    setTimeout(() => {
      setIsExiting(false)
      onClose()
    }, 250)
  }
  
  // 点击外部关闭菜单
  useEffect(() => {
    const handleClickOutside = () => {
      setExpandedMenuId(null)
      setUserMenuOpen(false)
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])
  
  // 桌面端：始终渲染，通过CSS控制显示/隐藏
  if (!isOpen && !isDesktop) return null

  const handleDeletePerson = (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    setDeleteConfirmId(id)
  }

  const confirmDeletePerson = async () => {
    if (deleteConfirmId === null) return
    const id = deleteConfirmId
    setDeleteConfirmId(null)
    try {
      await deletePerson(id)
      deletePersonChat(id)
      setExpandedMenuId(null)
      if (location.pathname === `/chat/${id}`) {
        navigate('/', { replace: true })
        handleClose()
      }
    } catch (err: any) {
      console.error('[HistoryPanel] 删除person失败:', id, err)
      alert(`删除失败: ${err?.message || String(err)}`)
    }
  }

  const handleStartEdit = (person: Person) => {
    setEditingId(person.id)
    // 默认显示出生年月日时间
    setEditName(person.name || `${person.birth_date} ${person.birth_time}`)
    setExpandedMenuId(null) // 关闭菜单
  }

  const handleSaveEdit = (id: number) => {
    if (editName.trim()) {
      // 校验名称唯一性
      const exists = persons.some(p => p.id !== id && p.name === editName.trim())
      if (exists) {
        alert('名称已存在，请输入不同的名称')
        return
      }
      renamePerson(id, editName.trim())
    }
    setEditingId(null)
    setEditName('')
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditName('')
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const handleGoRecharge = () => {
    setUserMenuOpen(false)
    if (isDesktop) {
      navigate('/recharge')
    } else {
      handleClose()
      setTimeout(() => navigate('/recharge'), 260)
    }
  }

  const handleGoPoints = () => {
    setUserMenuOpen(false)
    if (isDesktop) {
      navigate('/points')
    } else {
      handleClose()
      setTimeout(() => navigate('/points'), 260)
    }
  }

  const handleOpenNicknameModal = () => {
    setUserMenuOpen(false)
    setNickname(user?.name || '')
    setShowNicknameModal(true)
  }

  const handleSaveNickname = async () => {
    const name = nickname.trim()
    if (!name) return
    setSavingNickname(true)
    try {
      const { data } = await authApi.updateProfile(name)
      if (user) {
        setUser({ ...user, name: data.name })
      }
      setShowNicknameModal(false)
    } catch (err: any) {
      alert(err?.response?.data?.detail || '昵称修改失败')
    } finally {
      setSavingNickname(false)
    }
  }

  return (
    <>
      {/* 遮罩层 - 展开时显示，点击空白区域收起 */}
      {isOpen && <div className="history-panel-overlay" onClick={handleClose} />}

      {/* 侧滑面板 */}
      <div className={`history-panel ${isDesktop ? 'history-panel-desktop' : ''} ${isDesktop && !isOpen ? 'panel-exit' : ''} ${!isDesktop && isExiting ? 'panel-exit' : ''}`}>
        {/* 顶部栏 - 品牌logo + 品牌名 + 收起按钮 */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid #C9B5A1' }}>
          {/* 左侧：品牌logo + 品牌名 */}
          <div className="flex items-center gap-3">
            <span className="logo-text" style={{ color: '#44403d' }}>趣算算</span>
          </div>
          {/* 右侧：收起按钮 */}
          <button onClick={handleClose} style={{ color: '#846456' }} className="hover:text-gray-600 text-lg leading-none p-1">
            {isDesktop ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18l-6-6 6-6" />
              </svg>
            ) : (
              '×'
            )}
          </button>
        </div>

        {/* 人物列表 */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {/* 分析历史标题 */}
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-500">分析历史</h2>
          </div>
          {persons.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <div className="text-4xl mb-3">📋</div>
              <p className="text-sm">暂无分析记录</p>
              <p className="text-xs mt-1">添加人物信息开始推算</p>
            </div>
          ) : (
            <div className="space-y-2">
              {persons.map((person) => (
                <div
                  key={person.id}
                  onClick={() => {
                    if (editingId !== person.id) {
                      // 桌面端直接导航，不关闭面板
                      if (isDesktop) {
                        onNavigateToChat(person.id)
                      } else {
                        handleClose()
                        setTimeout(() => onNavigateToChat(person.id), 260)
                      }
                    }
                  }}
                  className="flex items-center justify-between p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-all cursor-pointer active:scale-[0.98]"
                >
                  <div className="flex-1 min-w-0">
                    {editingId === person.id ? (
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveEdit(person.id)
                            if (e.key === 'Escape') handleCancelEdit()
                          }}
                          className="flex-1 px-3 py-2 border border-primary-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                          autoFocus
                        />
                        <button
                          onClick={() => handleSaveEdit(person.id)}
                          className="text-primary-600 text-sm font-medium px-2"
                        >
                          确定
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="text-gray-400 text-sm px-2"
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <>
                        <h3 className="font-medium text-gray-800 text-sm truncate">
                          {person.name || `${person.birth_date} ${person.birth_time}`}
                        </h3>
                        <p className="text-gray-400 text-xs">
                          {person.birth_place} · {person.calendar_type === 'solar' ? '公历' : '农历'} · {genderToText(person.gender)}
                        </p>
                      </>
                    )}
                  </div>
                  {editingId !== person.id && (
                    <div className="relative">
                      {/* 更多操作按钮 */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setExpandedMenuId(expandedMenuId === person.id ? null : person.id)
                        }}
                        className="text-gray-400 hover:text-gray-600 text-xs p-1 transition-colors"
                      >
                        ⋮
                      </button>
                      {/* 下拉菜单 */}
                      {expandedMenuId === person.id && (
                        <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50 min-w-[80px]">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleStartEdit(person)
                            }}
                            className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-primary-500"
                          >
                            编辑
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeletePerson(e, person.id)
                            }}
                            className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-red-400"
                          >
                            删除
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 底部固定区域 */}
        <div className="border-t border-gray-100 px-4 py-4" style={{ paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}>
          {/* 添加新分析按钮 */}
          <button
            onClick={() => {
              // 桌面端直接导航，不关闭面板
              if (isDesktop) {
                onNavigateToAddPerson()
              } else {
                handleClose()
                setTimeout(() => onNavigateToAddPerson(), 260)
              }
            }}
            className="w-full py-3 rounded-xl font-medium mb-4 transition-all"
            style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
          >
            ＋ 添加新分析
          </button>

          {/* 用户信息 */}
          <div className="flex items-center space-x-3 px-1">
            <div className="w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-sm" style={{ backgroundColor: '#8b6f5a' }}>
              {user?.name?.[0] || '?'}
            </div>
            <div className="flex-1">
              <p className="text-gray-800 text-sm font-medium">{user?.name || '未登录'}</p>
              <p className="text-gray-400 text-xs">剩余积分：{user?.points || 0}</p>
            </div>
            {/* 更多功能入口 */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setUserMenuOpen(!userMenuOpen)
                }}
                className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                aria-label="更多功能"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 bottom-full mb-1 bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50 min-w-[110px]">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleGoRecharge()
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-primary-500"
                  >
                    购买积分
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleGoPoints()
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-primary-500"
                  >
                    积分明细
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleOpenNicknameModal()
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-primary-500"
                  >
                    用户信息
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setUserMenuOpen(false)
                      handleLogout()
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 hover:text-red-400"
                  >
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 自定义删除确认弹窗（底部弹出，不显示来源地址） */}
      {deleteConfirmId !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setDeleteConfirmId(null)}
        >
          <div
            className="w-full max-w-md bg-white rounded-2xl p-5 shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <p className="text-gray-800 text-base font-medium mb-1">删除后所有内容不可恢复</p>
            <p className="text-gray-500 text-sm mb-5">请确认是否删除</p>
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="flex-1 py-2.5 rounded-lg border border-gray-200 text-gray-600 text-sm hover:bg-gray-50 transition-all"
              >
                取消
              </button>
              <button
                onClick={confirmDeletePerson}
                className="flex-1 py-2.5 rounded-lg bg-red-500 text-white text-sm hover:bg-red-600 transition-all"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 修改昵称弹窗 */}
      {showNicknameModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setShowNicknameModal(false)}
        >
          <div
            className="w-full max-w-md bg-white rounded-2xl p-5 shadow-xl"
            onClick={e => e.stopPropagation()}
          >
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
              <button
                onClick={() => setShowNicknameModal(false)}
                className="flex-1 py-2.5 rounded-lg border border-gray-200 text-gray-600 text-sm hover:bg-gray-50 transition-all"
              >
                取消
              </button>
              <button
                onClick={handleSaveNickname}
                disabled={savingNickname || !nickname.trim()}
                className="flex-1 py-2.5 rounded-lg text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
              >
                {savingNickname ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
