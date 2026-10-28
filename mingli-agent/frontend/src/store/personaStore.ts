import { create } from 'zustand'
import {
  personaApi,
  type Persona,
  type PersonaConversation,
  type PersonaMessage,
} from '../api/persona'

interface PersonaState {
  personas: Persona[]
  conversations: PersonaConversation[]
  messages: PersonaMessage[]
  currentConversation: PersonaConversation | null
  isLoading: boolean
  error: string | null
  fetchPersonas: () => Promise<Persona[]>
  createPersona: (personId: number) => Promise<Persona>
  fetchConversations: (personaId: number) => Promise<void>
  createConversation: (personaId: number) => Promise<PersonaConversation>
  fetchMessages: (conversationId: number) => Promise<void>
  clearPersonaData: () => void
}

export const usePersonaStore = create<PersonaState>((set, get) => ({
  personas: [],
  conversations: [],
  messages: [],
  currentConversation: null,
  isLoading: false,
  error: null,

  fetchPersonas: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await personaApi.list()
      set({ personas: data, isLoading: false })
      return data
    } catch (error: any) {
      set({
        isLoading: false,
        error: error?.response?.data?.message || error?.response?.data?.detail || '命局人格加载失败',
      })
      throw error
    }
  },

  createPersona: async (personId) => {
    const { data } = await personaApi.create(personId)
    set({ personas: [data, ...get().personas.filter((item) => item.persona_id !== data.persona_id)] })
    return data
  },

  fetchConversations: async (personaId) => {
    const { data } = await personaApi.listConversations(personaId)
    set({ conversations: data })
  },

  createConversation: async (personaId) => {
    const { data } = await personaApi.createConversation(personaId)
    set({ conversations: [data, ...get().conversations] })
    return data
  },

  fetchMessages: async (conversationId) => {
    const { data } = await personaApi.getMessages(conversationId)
    set({ messages: data.items, currentConversation: data.conversation })
  },
  clearPersonaData: () => set({
    personas: [],
    conversations: [],
    messages: [],
    currentConversation: null,
    isLoading: false,
    error: null,
  }),
}))
