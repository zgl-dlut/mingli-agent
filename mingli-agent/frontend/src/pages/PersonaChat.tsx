import { FormEvent, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { personaApi, type PersonaMessage } from '../api/persona'
import { usePersonaStore } from '../store/personaStore'
import { color } from '../theme/tokens'

export default function PersonaChat() {
  const navigate = useNavigate()
  const { conversationId } = useParams<{ conversationId: string }>()
  const id = Number(conversationId)
  const { messages, currentConversation, fetchMessages } = usePersonaStore()
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [restReminder, setRestReminder] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (id) void fetchMessages(id).catch(() => setError('会话加载失败'))
  }, [fetchMessages, id])

  useEffect(() => {
    setRestReminder(currentConversation?.rest_reminder_required === true)
  }, [currentConversation?.conversation_id, currentConversation?.rest_reminder_required])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamText])

  const send = async (event: FormEvent) => {
    event.preventDefault()
    const content = input.trim()
    if (!content || sending || !id) return
    setInput('')
    setSending(true)
    setError(null)
    setStreamText('')
    try {
      await personaApi.sendMessage(id, content, {
        onMeta: (meta) => setRestReminder(meta.rest_reminder_required),
        onDelta: (text) => setStreamText((current) => current + text),
        onDone: (done) => {
          if (done.text) setStreamText(done.text)
        },
      })
      await fetchMessages(id)
      setStreamText('')
    } catch (requestError: any) {
      const data = requestError?.data
      setError(data?.message || requestError?.message || '发送失败')
    } finally {
      setSending(false)
    }
  }

  const visibleMessages: PersonaMessage[] = messages
  const reachedLimit = (currentConversation?.remaining_turns ?? 20) <= 0

  return (
    <div className="flex h-full min-h-0 flex-col" style={{ backgroundColor: color.bg }}>
      <header className="flex flex-none items-center px-3 py-3" style={{ borderBottom: `1px solid ${color.divider}` }}>
        <button onClick={() => navigate('/persona')} aria-label="返回" className="w-8 text-xl" style={{ color: color.ink }}>‹</button>
        <div className="flex-1 text-center">
          <div className="text-sm font-bold" style={{ color: color.ink }}>{currentConversation?.title || '命局人格'}</div>
          <div className="text-[10px]" style={{ color: color.ink2 }}>AI 生成 · 命局人格模拟</div>
        </div>
        <span className="w-8 text-right text-[10px]" style={{ color: color.ink2 }}>
          {currentConversation ? `${currentConversation.user_turn_count}/20` : ''}
        </span>
      </header>

      {restReminder && (
        <div className="flex-none px-4 py-2 text-xs leading-5" style={{ color: '#8A5B20', backgroundColor: '#F8F0DF' }}>
          已连续使用两小时，建议先休息一下，稍后再继续。
        </div>
      )}

      <main className="flex-1 min-h-0 overflow-y-auto px-4 py-4">
        {visibleMessages.length === 0 && !sending && (
          <div className="py-16 text-center">
            <div className="text-sm font-semibold" style={{ color: color.ink }}>从此刻的真实感受开始</div>
            <p className="mt-2 text-xs" style={{ color: color.ink2 }}>这里不是解盘报告，可以直接说正在发生的事。</p>
          </div>
        )}
        <div className="space-y-3">
          {visibleMessages.map((message) => (
            <div key={message.message_id} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div
                className="max-w-[84%] px-3.5 py-2.5 text-sm leading-6"
                style={{
                  backgroundColor: message.role === 'user' ? color.brand : color.card,
                  color: message.role === 'user' ? '#fff' : color.ink,
                  borderRadius: message.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                }}
              >
                {message.content}
              </div>
            </div>
          ))}
          {streamText && (
            <div className="flex justify-start">
              <div className="max-w-[84%] px-3.5 py-2.5 text-sm leading-6" style={{ backgroundColor: color.card, color: color.ink, borderRadius: '14px 14px 14px 4px' }}>
                {streamText}
              </div>
            </div>
          )}
          {sending && !streamText && <div className="text-xs" style={{ color: color.ink2 }}>正在回应…</div>}
          <div ref={endRef} />
        </div>
      </main>

      {error && <div className="flex-none px-4 py-2 text-xs" style={{ color: color.danger }}>{error}</div>}
      <form onSubmit={send} className="flex flex-none items-end gap-2 px-3 py-3" style={{ backgroundColor: color.card, borderTop: `1px solid ${color.divider}` }}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={sending || reachedLimit}
          rows={1}
          maxLength={2000}
          placeholder={reachedLimit ? '本次会话已满，请新建会话' : '说说此刻正在发生什么…'}
          className="min-h-10 max-h-24 flex-1 resize-none px-3 py-2.5 text-sm outline-none disabled:opacity-60"
          style={{ backgroundColor: color.bg, color: color.ink, borderRadius: '10px' }}
        />
        <button
          type="submit"
          disabled={!input.trim() || sending || reachedLimit}
          aria-label="发送"
          className="grid h-10 w-10 flex-none place-items-center text-white disabled:opacity-40"
          style={{ backgroundColor: color.brand, borderRadius: '10px' }}
        >
          ↑
        </button>
      </form>
    </div>
  )
}
