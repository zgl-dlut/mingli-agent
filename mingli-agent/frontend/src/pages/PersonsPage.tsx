import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'
import { useChatStore, allChats } from '../store/chatStore'
import { isApp } from '../utils/platform'
import { personApi } from '../api/person'
import type { Person } from '../types'

/**
 * 我的档案页
 * 分两个区块：
 * - 分析历史：有过 AI 咨询（存在聊天记录）的档案
 * - 全部档案：所有已建档案（含尚未咨询的），支持改名/删除/进入对话/看命盘
 */
export default function PersonsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // 选择模式（从对话页「星盘·昵称」模块进入）：点卡片选中即回对话页；current 高亮当前对话人物
  const picker = searchParams.get('picker') === '1'
  const currentId = Number(searchParams.get('current')) || null
  const { persons, fetchPersons, deletePerson } = usePersonStore()
  const { fetchUserInfo } = useUserStore()
  const { deletePersonChat } = useChatStore()

  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const [editingPersonId, setEditingPersonId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)

  useEffect(() => {
    if (persons.length === 0) fetchPersons()
  }, [persons.length, fetchPersons])

  const historyPersons = persons.filter((p) => (allChats[p.id]?.messages?.length || 0) > 0)

  // 点击页面其他区域时关闭操作菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (openMenuId !== null && !(event.target as Element).closest('.person-menu-btn') && !(event.target as Element).closest('.person-menu-dropdown')) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [openMenuId])

  // 编辑人物时同步后端数据，防止过期数据覆盖输入
  useEffect(() => {
    if (editingPersonId !== null) fetchPersons()
  }, [editingPersonId, fetchPersons])

  const handleStartEdit = (personId: number, currentName: string) => {
    setEditingPersonId(personId)
    setEditingName(currentName)
  }

  const handleSaveEdit = async (personId: number) => {
    if (editingName.trim()) {
      try {
        await personApi.update(personId, { name: editingName.trim() })
        await fetchPersons()
        setEditingPersonId(null)
        setEditingName('')
      } catch {
        alert('修改失败，请重试')
      }
    }
  }

  const handleCancelEdit = () => {
    setEditingPersonId(null)
    setEditingName('')
  }

  const confirmDeletePerson = useCallback(async () => {
    if (deleteConfirmId === null) return
    try {
      await deletePerson(deleteConfirmId)
      deletePersonChat(deleteConfirmId)
      fetchUserInfo()
      setDeleteConfirmId(null)
      setOpenMenuId(null)
    } catch (err: any) {
      const status = err?.response?.status
      const errorCode = err?.response?.data?.error_code
      if (status === 404 || errorCode === 'PERSON_NOT_FOUND' || errorCode === 3002) {
        await fetchPersons()
        setDeleteConfirmId(null)
        setOpenMenuId(null)
        alert('该人物档案已被删除，列表已刷新')
      } else if (status === 403 || errorCode === 'PERMISSION_DENIED' || errorCode === 2002) {
        alert('无权限删除此人物档案，请重新登录后再试')
      } else if (status === 401 || errorCode === 'UNAUTHORIZED' || errorCode === 2001) {
        alert('登录已过期，请重新登录')
        navigate('/login')
      } else {
        alert('删除失败，请重试')
      }
    }
  }, [deleteConfirmId, deletePerson, deletePersonChat, fetchUserInfo, fetchPersons, navigate])

  const handleMenuClick = (e: React.MouseEvent, personId: number) => {
    e.stopPropagation()
    setOpenMenuId(openMenuId === personId ? null : personId)
  }

  const renderPersonItem = (person: Person) => (
    <div
      key={person.id}
      onClick={() => {
        if (editingPersonId !== person.id) navigate(`/chat/${person.id}`)
      }}
      className="flex items-center justify-between px-3 py-3 border-b border-gray-50 last:border-b-0 cursor-pointer hover:bg-gray-50 transition-colors"
    >
      {/* 选择模式：左侧单选圈，当前对话人物打勾 */}
      {picker && (
        <span
          className="flex-none w-5 h-5 rounded-full border flex items-center justify-center mr-2"
          style={person.id === currentId
            ? { backgroundColor: '#4A4E8F', borderColor: '#4A4E8F', color: '#FFFFFF' }
            : { borderColor: '#D8D5CE' }}
        >
          {person.id === currentId && <span className="text-[11px] leading-none">✓</span>}
        </span>
      )}
      <div className="flex-1 min-w-0">
        {editingPersonId === person.id ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={editingName}
              onChange={(e) => setEditingName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveEdit(person.id)
                if (e.key === 'Escape') handleCancelEdit()
              }}
              className="flex-1 px-2 py-1 text-sm border border-primary-500 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
            <button onClick={(e) => { e.stopPropagation(); handleSaveEdit(person.id) }} className="text-primary-500 hover:text-primary-600 text-sm">✓</button>
            <button onClick={(e) => { e.stopPropagation(); handleCancelEdit() }} className="text-gray-500 hover:text-gray-600 text-sm">✕</button>
          </div>
        ) : (
          <div className="text-sm font-medium text-gray-800 truncate">{person.name}</div>
        )}
        <div className="text-xs text-gray-500 mt-0.5">
          {person.birth_date} {person.birth_time}
          {person.calendar_type === 'lunar' ? ' · 农历' : ''}
        </div>
      </div>
      <div className="flex items-center gap-2 ml-3 flex-none">
        {isApp() && (
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/chart/${person.id}`) }}
            className="text-xs rounded-full px-2.5 py-1"
            style={{ backgroundColor: '#F5F0E8', color: '#4A4E8F' }}
          >
            看命盘
          </button>
        )}
        <button
          onClick={(e) => handleMenuClick(e, person.id)}
          className="person-menu-btn text-gray-400 hover:text-gray-600 transition-colors p-1"
        >
          <span className="text-lg leading-none">⋮</span>
        </button>
        {openMenuId === person.id && (
          <div className="person-menu-dropdown absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-10 min-w-[120px]">
            <button
              onClick={(e) => { e.stopPropagation(); handleStartEdit(person.id, person.name); setOpenMenuId(null) }}
              className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              编辑
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setDeleteConfirmId(person.id) }}
              className="w-full text-left px-4 py-2 text-sm text-red-400 hover:bg-gray-50 transition-colors"
            >
              删除
            </button>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <div className="px-4 py-4 pb-6" style={{ maxWidth: '430px', margin: '0 auto' }}>
      {/* 选择模式标题栏（从对话页进入）：返回 + 选择档案 */}
      {picker && (
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => navigate(-1)} className="text-gray-700 text-xl leading-none px-1" aria-label="返回">‹</button>
          <span className="text-base font-semibold text-gray-800">选择档案</span>
          <span className="w-6" />
        </div>
      )}
      {/* 分析历史：有 AI 咨询记录的档案 */}
      <div className="bg-white rounded-2xl shadow-sm">
        <div className="px-4 pt-3 pb-1 text-xs text-gray-500">分析历史</div>
        {historyPersons.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-gray-400 text-sm">暂无咨询记录</p>
            <p className="text-gray-300 text-xs mt-1">完成一次 AI 咨询后，记录会出现在这里</p>
          </div>
        ) : (
          <div className="relative">{historyPersons.map(renderPersonItem)}</div>
        )}
      </div>

      {/* 全部档案 */}
      <div className="bg-white rounded-2xl shadow-sm mt-3">
        <div className="px-4 pt-3 pb-1 text-xs text-gray-500">全部档案</div>
        {persons.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-400 text-sm">暂无档案</div>
        ) : (
          <div className="relative">{persons.map(renderPersonItem)}</div>
        )}
      </div>

      {/* 添加新档案：保存后自动回到对话页 */}
      <button
        onClick={() => navigate('/', { replace: true, state: { timestamp: Date.now() } })}
        className="w-full mt-3 bg-white rounded-2xl px-4 py-3.5 text-sm text-left transition-colors hover:bg-gray-50"
        style={{ color: '#4A4E8F' }}
      >
        {picker ? '+ 添加档案' : '+ 添加新分析'}
      </button>

      {/* 删除确认弹窗 */}
      {deleteConfirmId !== null && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30" onClick={() => setDeleteConfirmId(null)}>
          <div className="w-full max-w-md bg-white rounded-2xl p-5 shadow-xl mx-4" onClick={(e) => e.stopPropagation()}>
            <p className="text-gray-800 text-base font-medium mb-1">删除后所有内容不可恢复</p>
            <p className="text-gray-500 text-sm mb-5">请确认是否删除</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteConfirmId(null)} className="flex-1 py-2.5 rounded-lg border border-gray-200 text-gray-600 text-sm">
                取消
              </button>
              <button onClick={confirmDeletePerson} className="flex-1 py-2.5 rounded-lg bg-red-500 text-white text-sm">
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
