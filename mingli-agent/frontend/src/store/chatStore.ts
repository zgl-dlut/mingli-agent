import { create } from 'zustand'
import type { ChatMessage } from '../types'
import { chatApi } from '../api/chat'
import { createLogger } from '../utils/logger'

const logger = createLogger('chatStore')
const STORAGE_KEY = 'mingli_chats'

interface PersonChat {
  personId: number
  messages: ChatMessage[]
  firstReadingGenerated: boolean
}

let nextMessageId = 1

function loadAllChats(): Record<number, PersonChat> {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    try {
      const data = JSON.parse(stored)
      // 更新消息自增 id
      const allMessages: ChatMessage[] = []
      Object.values(data).forEach((chat: any) => {
        if (chat?.messages) allMessages.push(...chat.messages)
      })
      const maxId = allMessages.reduce((max, m) => Math.max(max, m.id), 0)
      nextMessageId = maxId + 1
      const totalMsgs = allMessages.length
      const personIds = Object.keys(data)
      logger.info(`loadAllChats 完成`, { personCount: personIds.length, totalMsgs, nextMessageId })
      return data
    } catch (e) {
      logger.error('loadAllChats 解析失败', String(e))
      return {}
    }
  }
  logger.debug('loadAllChats: localStorage 中无数据')
  return {}
}

function saveAllChats(chats: Record<number, PersonChat>) {
  const totalMsgs = Object.values(chats).reduce((sum, c) => sum + (c.messages?.length || 0), 0)
  logger.debug(`saveAllChats`, { personCount: Object.keys(chats).length, totalMsgs })
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats))
}

interface ChatStore {
  messages: ChatMessage[]
  currentPersonId: number | null
  isGenerating: boolean
  currentMessage: string
  streamingPersonId: number | null
  error: string | null
  fetchMessages: (personId: number, sessionId: number) => Promise<void>
  addMessage: (personId: number, role: 'user' | 'assistant', content: string) => void
  setCurrentPerson: (personId: number) => void
  setCurrentMessage: (content: string, personId?: number | null) => void
  setIsGenerating: (generating: boolean, personId?: number | null) => void
  clearMessages: () => void
  hasFirstReading: (personId: number) => boolean
  setFirstReadingGenerated: (personId: number) => void
  deletePersonChat: (personId: number) => void
  deleteAllChats: () => void
}

let allChats: Record<number, PersonChat> = loadAllChats()

/** 导出 allChats 供外部去重使用（只读引用） */
export { allChats }

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  currentPersonId: null,
  isGenerating: false,
  currentMessage: '',
  streamingPersonId: null,
  error: null,
  fetchMessages: async (personId, sessionId) => {
    logger.info(`fetchMessages`, { personId, sessionId })
    try {
      const remoteMessages = await chatApi.getMessages(sessionId)
      const mapped: ChatMessage[] = remoteMessages.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: m.created_at,
      }))
      if (!allChats[personId]) {
        allChats[personId] = { personId, messages: [], firstReadingGenerated: false }
      }
      allChats[personId].messages = mapped
      saveAllChats(allChats)
      set({ messages: mapped, currentPersonId: personId, currentMessage: '', isGenerating: false, streamingPersonId: null })
    } catch (e) {
      logger.error(`fetchMessages 拉取失败，降级读本地缓存`, String(e))
      const chat = allChats[personId]
      set({ messages: chat?.messages || [], currentPersonId: personId, currentMessage: '', isGenerating: false, streamingPersonId: null })
    }
  },
  addMessage: (personId, role, content) => {
    const addId = `addMsg#${Date.now().toString(36)}`
    const chat = allChats[personId]
    const allMsgs = chat?.messages || []
    const lastMsg = allMsgs.length > 0 ? allMsgs[allMsgs.length - 1] : null

    logger.info(`${addId} 被调用`, {
      role,
      personId,
      currentMsgCount: allMsgs.length,
      lastMsgRole: lastMsg?.role || 'none',
      lastMsgId: lastMsg?.id || 'none',
      lastMsgPreview: lastMsg ? lastMsg.content.slice(0, 40) : 'none',
      contentPreview: content.slice(0, 40),
      callerStack: new Error().stack?.split('\n').slice(2, 4).map(s => s.trim()).join(' <- ') || 'unknown',
    })

    // 🛡️ 去重层：如果正在添加的是用户消息，且与上一条用户消息内容完全相同且相邻
    if (role === 'user' && allMsgs.length > 0) {
      if (lastMsg?.role === 'user' && lastMsg?.content === content) {
        logger.warn(`${addId} 去重拦截：上一条是相同的用户消息`, {
          lastMsgId: lastMsg.id,
          lastMsgContent: lastMsg.content.slice(0, 40),
          newContent: content.slice(0, 40),
        })
        return
      }
    }

    // 🛡️ 去重层2：检查最近2条内是否有完全相同的 assistant 消息（防止 SSE + recovery 双重写入）
    if (role === 'assistant' && content.length > 20 && allMsgs.length > 0) {
      const recentAssistantMsgs = allMsgs.slice(-3).filter(m => m.role === 'assistant')
      const duplicate = recentAssistantMsgs.find(m => m.content === content)
      if (duplicate) {
        logger.warn(`${addId} 去重拦截：最近消息中已有相同的assistant消息`, {
          dupMsgId: duplicate.id,
          dupContentPreview: duplicate.content.slice(0, 40),
          recentCount: recentAssistantMsgs.length,
        })
        return
      }
    }

    const message: ChatMessage = {
      id: nextMessageId++,
      role,
      content,
      created_at: new Date().toISOString(),
    }

    if (!allChats[personId]) {
      allChats[personId] = { personId, messages: [], firstReadingGenerated: false }
    }
    allChats[personId].messages.push(message)
    logger.success(`${addId} ✅ 实际插入`, {
      msgId: message.id,
      role,
      personId,
      newMsgCount: allChats[personId].messages.length,
      contentPreview: content.slice(0, 40),
    })
    saveAllChats(allChats)

    set((state) => {
      if (state.currentPersonId !== personId) {
        logger.warn(`${addId} currentPersonId不匹配，不更新Zustand state`, {
          expected: personId,
          actual: state.currentPersonId,
        })
        return {}
      }
      logger.debug(`${addId} 更新Zustand`, {
        oldLen: state.messages.length,
        newLen: state.messages.length + 1,
        newMsgId: message.id,
        newMsgRole: role,
      })
      return { messages: [...state.messages, message] }
    })
  },
  setCurrentPerson: (personId) => {
    const chat = allChats[personId]
    logger.info(`setCurrentPerson`, { personId, msgCount: chat?.messages?.length || 0 })
    set({ currentPersonId: personId, messages: chat?.messages || [], currentMessage: '', isGenerating: false, streamingPersonId: null })
  },
  setCurrentMessage: (content, personId = null) => {
    logger.debug(`setCurrentMessage`, { personId, contentLen: content?.length || 0 })
    set({ currentMessage: content, streamingPersonId: personId })
  },
  setIsGenerating: (generating, personId = null) => {
    logger.info(`setIsGenerating`, { generating, personId })
    set({ isGenerating: generating, streamingPersonId: generating ? personId : null })
  },
  clearMessages: () => set({ messages: [], currentMessage: '', streamingPersonId: null }),
  hasFirstReading: (personId) => {
    return allChats[personId]?.firstReadingGenerated === true
  },
  setFirstReadingGenerated: (personId) => {
    logger.success(`setFirstReadingGenerated`, { personId })
    if (!allChats[personId]) {
      allChats[personId] = { personId, messages: [], firstReadingGenerated: false }
    }
    allChats[personId].firstReadingGenerated = true
    saveAllChats(allChats)
  },
  deletePersonChat: (personId) => {
    delete allChats[personId]
    saveAllChats(allChats)
    set((state) => {
      if (state.currentPersonId === personId) {
        return { messages: [], currentPersonId: null, currentMessage: '', streamingPersonId: null }
      }
      return {}
    })
  },
  deleteAllChats: () => {
    allChats = {}
    saveAllChats(allChats)
    set({ messages: [], currentPersonId: null, currentMessage: '', streamingPersonId: null })
  },
}))
