import apiClient from './client'

export interface Persona {
  persona_id: number
  person_id: number
  name: string
  avatar_key: string
  profile: {
    day_master?: { stem?: string; element?: string; yin_yang?: string }
    tone?: string
    traits?: string[]
    boundaries?: string[]
  }
  prompt_version: string
  created_at: string
}

export interface PersonaConversation {
  conversation_id: number
  persona_id: number
  title: string
  user_turn_count: number
  remaining_turns: number
  started_at: string
  last_message_at: string
  closed_at: string | null
  rest_reminder_required: boolean
}

export interface PersonaMessage {
  message_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  safety_category: string | null
  created_at: string
}

export interface PersonaMemory {
  enabled: boolean
  preferred_name: string | null
  current_context: string[]
  preferences: string[]
  important_relationships: Array<{ label: string; summary: string }>
  stage_summary: string
  updated_at: string | null
}

export interface PersonaStreamMeta {
  message_id: number
  rest_reminder_required: boolean
  safety_category?: string
}

export interface PersonaStreamDone {
  text?: string
  user_turn_count: number
  remaining_turns: number
}

export const personaApi = {
  list: () => apiClient.get<Persona[]>('/personas'),
  get: (personaId: number) => apiClient.get<Persona>(`/personas/${personaId}`),
  create: (personId: number, name?: string) =>
    apiClient.post<Persona>('/personas', { person_id: personId, name }),
  listConversations: (personaId: number) =>
    apiClient.get<PersonaConversation[]>(`/personas/${personaId}/conversations`),
  createConversation: (personaId: number, title?: string) =>
    apiClient.post<PersonaConversation>(`/personas/${personaId}/conversations`, { title }),
  getMessages: (conversationId: number) =>
    apiClient.get<{ items: PersonaMessage[]; conversation: PersonaConversation }>(
      `/persona-conversations/${conversationId}/messages`,
    ),
  getMemory: (personaId: number) =>
    apiClient.get<PersonaMemory>(`/personas/${personaId}/memory`),
  updateMemory: (personaId: number, enabled: boolean) =>
    apiClient.patch<PersonaMemory>(`/personas/${personaId}/memory-settings`, { enabled }),
  clearMemory: (personaId: number) =>
    apiClient.delete(`/personas/${personaId}/memory`),

  sendMessage: async (
    conversationId: number,
    content: string,
    handlers: {
      onMeta?: (data: PersonaStreamMeta) => void
      onDelta?: (text: string) => void
      onDone?: (data: PersonaStreamDone) => void
    },
  ) => {
    const token = localStorage.getItem('mingli_token')
    const response = await fetch(`/api/persona-conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      const error = new Error(body.message || body.detail || '发送失败') as Error & { data?: unknown; status?: number }
      error.data = body
      error.status = response.status
      throw error
    }
    const reader = response.body?.getReader()
    if (!reader) throw new Error('响应流不可用')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''
      for (const raw of events) {
        const lines = raw.split('\n')
        const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim()
        const dataLine = lines.find((line) => line.startsWith('data:'))?.slice(5).trim()
        if (!event || !dataLine) continue
        const data = JSON.parse(dataLine)
        if (event === 'meta') handlers.onMeta?.(data)
        if (event === 'delta') handlers.onDelta?.(data.text || '')
        if (event === 'done') handlers.onDone?.(data)
      }
      if (done) break
    }
  },
}
