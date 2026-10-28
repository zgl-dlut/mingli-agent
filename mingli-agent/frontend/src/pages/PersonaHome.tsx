import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useEntitlementStore } from '../store/entitlementStore'
import { usePersonStore } from '../store/personStore'
import { usePersonaStore } from '../store/personaStore'
import { color, radius, shadow } from '../theme/tokens'

const ELEMENT_BG: Record<string, string> = {
  wood: '#347B68',
  fire: '#B75C55',
  earth: '#A47B43',
  metal: '#66717D',
  water: '#47738F',
  unknown: color.brand,
}

export default function PersonaHome() {
  const navigate = useNavigate()
  const { persons, fetchPersons } = usePersonStore()
  const { entitlement, fetchEntitlement } = useEntitlementStore()
  const {
    personas,
    conversations,
    isLoading,
    error,
    fetchPersonas,
    createPersona,
    fetchConversations,
    createConversation,
  } = usePersonaStore()
  const [creating, setCreating] = useState(false)
  const persona = personas[0]
  const selfPerson = useMemo(() => persons.find((person) => person.is_self), [persons])

  useEffect(() => {
    void fetchPersons()
    void fetchEntitlement()
    void fetchPersonas().catch(() => undefined)
  }, [fetchEntitlement, fetchPersonas, fetchPersons])

  useEffect(() => {
    if (persona) void fetchConversations(persona.persona_id)
  }, [fetchConversations, persona])

  const handleCreatePersona = async () => {
    if (!selfPerson) {
      navigate('/')
      return
    }
    setCreating(true)
    try {
      await createPersona(selfPerson.id)
    } catch (requestError: any) {
      const data = requestError?.response?.data
      alert(data?.message || data?.detail || '创建失败')
    } finally {
      setCreating(false)
    }
  }

  const handleNewConversation = async () => {
    if (!persona) return
    setCreating(true)
    try {
      const conversation = await createConversation(persona.persona_id)
      navigate(`/persona/chat/${conversation.conversation_id}`)
    } catch (requestError: any) {
      const data = requestError?.response?.data
      if (data?.code === 'usage_limit_reached') navigate('/subscription?required=full')
      else alert(data?.message || data?.detail || '新建会话失败')
    } finally {
      setCreating(false)
    }
  }

  if (isLoading && !persona) {
    return <div className="py-20 text-center text-sm" style={{ color: color.ink2 }}>正在唤醒命局人格…</div>
  }

  if (!persona) {
    return (
      <div className="px-4 pb-8">
        <h1 className="m-0 text-xl font-bold" style={{ color: color.ink }}>对话</h1>
        <p className="mt-1 text-xs" style={{ color: color.ink2 }}>与基于本人命盘形成的 AI 人格对话</p>
        <div className="mt-5 p-5 text-center" style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card }}>
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-full text-2xl text-white" style={{ backgroundColor: color.brand }}>命</div>
          <div className="mt-4 text-base font-bold" style={{ color: color.ink }}>创建你的命局人格</div>
          <p className="mt-2 text-xs leading-6" style={{ color: color.ink2 }}>
            它会使用同一份命盘快照形成表达偏好，但不会冒充真人或替你作决定。
          </p>
          <button
            onClick={() => void handleCreatePersona()}
            disabled={creating}
            className="mt-4 w-full py-3 text-sm font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: color.brand, borderRadius: '10px' }}
          >
            {creating ? '创建中…' : selfPerson ? '创建命局人格' : '先建立本人档案'}
          </button>
          {error && <p className="mt-3 text-xs" style={{ color: color.danger }}>{error}</p>}
        </div>
      </div>
    )
  }

  const element = persona.profile.day_master?.element || 'unknown'
  const stem = persona.profile.day_master?.stem || '命'
  const remaining = entitlement?.persona_session_monthly.remaining

  return (
    <div className="px-4 pb-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="m-0 text-xl font-bold" style={{ color: color.ink }}>对话</h1>
          <p className="mt-1 text-xs" style={{ color: color.ink2 }}>AI 生成 · 命局人格模拟</p>
        </div>
        <button onClick={() => navigate(`/persona/${persona.persona_id}/memory`)} className="text-xs" style={{ color: color.brand }}>记忆设置</button>
      </div>

      <section className="mt-3 p-4" style={{ backgroundColor: color.card, borderRadius: radius.card, boxShadow: shadow.card }}>
        <div className="flex items-center gap-3">
          <div className="grid h-14 w-14 flex-none place-items-center rounded-full text-xl font-bold text-white" style={{ backgroundColor: ELEMENT_BG[element] || color.brand }}>{stem}</div>
          <div className="min-w-0">
            <div className="truncate text-base font-bold" style={{ color: color.ink }}>{persona.name}</div>
            <div className="mt-1 text-xs" style={{ color: color.ink2 }}>{persona.profile.traits?.slice(0, 2).join(' · ')}</div>
          </div>
        </div>
        <button
          onClick={() => void handleNewConversation()}
          disabled={creating}
          className="mt-4 w-full py-3 text-sm font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: color.brand, borderRadius: '10px' }}
        >
          {creating ? '正在新建…' : '开始新的对话'}
        </button>
        <div className="mt-2 text-center text-[11px]" style={{ color: color.ink2 }}>
          {remaining == null ? '本月会话不限' : `本月还可新建 ${remaining} 次会话`}
        </div>
      </section>

      <div className="mt-5 mb-2 text-sm font-bold" style={{ color: color.ink }}>最近会话</div>
      {conversations.length === 0 ? (
        <div className="py-8 text-center text-xs" style={{ color: color.ink2 }}>还没有对话记录</div>
      ) : (
        <div className="space-y-2">
          {conversations.map((conversation) => (
            <button
              key={conversation.conversation_id}
              onClick={() => navigate(`/persona/chat/${conversation.conversation_id}`)}
              className="w-full p-3.5 text-left"
              style={{ backgroundColor: color.card, borderRadius: '10px' }}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-semibold" style={{ color: color.ink }}>{conversation.title}</span>
                <span className="flex-none text-[10px]" style={{ color: color.ink2 }}>{conversation.user_turn_count}/20</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
