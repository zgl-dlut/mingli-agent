import { create } from 'zustand'
import { authApi, type UserInfo } from '../api/auth'
import { useChatStore } from './chatStore'
import { usePersonStore } from './personStore'
import { useTransactionStore } from './transactionStore'

interface UserState {
  user: UserInfo | null
  token: string | null
  isLoggedIn: boolean
  isLoading: boolean
  error: string | null

  // Actions
  sendSmsCode: (phone: string) => Promise<{ code?: string; dev_mode?: boolean }>
  loginWithSms: (phone: string, code: string) => Promise<void>
  logout: () => void
  fetchUserInfo: () => Promise<void>
  setUser: (user: UserInfo) => void
  addPoints: (points: number) => void
  deductPoints: (points: number) => boolean
  clearError: () => void
}

// Mock 模式开关：后端未启动时自动降级为本地 mock
const MOCK_MODE = false

export const useUserStore = create<UserState>((set, get) => ({
  user: JSON.parse(localStorage.getItem('mingli_user') || 'null'),
  token: localStorage.getItem('mingli_token'),
  isLoggedIn: !!localStorage.getItem('mingli_token'),
  isLoading: false,
  error: null,

  sendSmsCode: async (phone: string) => {
    try {
      set({ isLoading: true, error: null })
      if (MOCK_MODE) {
        // Mock 模式：直接返回，不请求后端
        set({ isLoading: false })
        return { code: '111111', dev_mode: true }
      }
      const { data } = await authApi.sendSms(phone)
      set({ isLoading: false })
      return data
    } catch (e: any) {
      set({ error: e.response?.data?.detail || '发送验证码失败', isLoading: false })
      throw e
    }
  },

  loginWithSms: async (phone: string, code: string) => {
    try {
      set({ isLoading: true, error: null })

      if (MOCK_MODE) {
        // Mock 模式：本地模拟登录
        const mockUser: UserInfo = {
          id: 1,
          phone: phone,
          name: `用户${phone.slice(-4)}`,
          avatar: null,
          points: 200,
          created_at: new Date().toISOString(),
        }
        localStorage.setItem('mingli_token', 'mock-token-' + Date.now())
        localStorage.setItem('mingli_user', JSON.stringify(mockUser))
        set({
          user: mockUser,
          token: 'mock-token-' + Date.now(),
          isLoggedIn: true,
          isLoading: false,
        })
        return
      }

      // 分享链接邀请参数：注册时带给后端（仅新用户注册会触发邀请人奖励）
      let inviterRef: string | null = null
      try {
        const raw = (localStorage.getItem('inviter_ref') || '').trim()
        if (/^[0-9A-Za-z]{1,12}$/.test(raw) && raw !== '0') inviterRef = raw
      } catch { /* ignore */ }

      const { data } = await authApi.login(phone, code, inviterRef)
      // 无论新老用户，登录后即清除邀请标记（老用户登录本就不发奖励）
      try { localStorage.removeItem('inviter_ref') } catch { /* ignore */ }

      const userInfo: UserInfo = {
        id: data.user_id,
        phone: data.phone,
        name: data.name,
        avatar: null,
        points: data.points,
        created_at: new Date().toISOString(),
      }

      localStorage.setItem('mingli_token', data.access_token)
      localStorage.setItem('mingli_user', JSON.stringify(userInfo))

      set({
        user: userInfo,
        token: data.access_token,
        isLoggedIn: true,
        isLoading: false,
      })
    } catch (e: any) {
      set({ error: e.response?.data?.detail || '登录失败', isLoading: false })
      throw e
    }
  },

  logout: () => {
    localStorage.removeItem('mingli_token')
    localStorage.removeItem('mingli_user')
    // 退出登录时清空本地所有用户数据，防止公用设备残留上一个用户的隐私数据
    useChatStore.getState().deleteAllChats()
    usePersonStore.getState().clearPersons()
    useTransactionStore.getState().clearTransactions()
    set({ user: null, token: null, isLoggedIn: false })
  },

  fetchUserInfo: async () => {
    try {
      const { data } = await authApi.getUserInfo()
      const userInfo: UserInfo = {
        id: data.id,
        phone: data.phone || '',
        name: data.name,
        avatar: data.avatar,
        points: data.points,
        created_at: data.created_at,
      }
      localStorage.setItem('mingli_user', JSON.stringify(userInfo))
      set({ user: userInfo })
    } catch {
      // 如果获取失败，保持本地状态
    }
  },

  setUser: (user: UserInfo) => {
    localStorage.setItem('mingli_user', JSON.stringify(user))
    set({ user, isLoggedIn: true })
  },

  addPoints: (points: number) => {
    const { user } = get()
    if (user) {
      const updated = { ...user, points: user.points + points }
      localStorage.setItem('mingli_user', JSON.stringify(updated))
      set({ user: updated })
    }
  },

  deductPoints: (points: number) => {
    const { user } = get()
    if (user && user.points >= points) {
      const updated = { ...user, points: user.points - points }
      localStorage.setItem('mingli_user', JSON.stringify(updated))
      set({ user: updated })
      return true
    }
    return false
  },

  clearError: () => set({ error: null }),
}))
