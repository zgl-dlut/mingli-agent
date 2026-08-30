/**
 * 认证 API
 */
import apiClient from './client'

export interface SendSmsResponse {
  message: string
  code?: string  // 开发模式返回
  dev_mode?: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  phone: string
  name: string
  points: number
}

export interface UserInfo {
  id: number
  phone: string
  name: string
  avatar: string | null
  points: number
  created_at: string
}

export const authApi = {
  /** 发送验证码 */
  sendSms: (phone: string) =>
    apiClient.post<SendSmsResponse>('/auth/send-sms', { phone }),

  /** 验证码登录 */
  login: (phone: string, code: string) =>
    apiClient.post<LoginResponse>('/auth/login', { phone, code }),

  /** 刷新 Token */
  refreshToken: (userId: number) =>
    apiClient.post('/auth/refresh', null, { params: { user_id: userId } }),

  /** 获取用户信息 */
  getUserInfo: () =>
    apiClient.get<UserInfo>('/user/profile'),

  /** 修改昵称 */
  updateProfile: (name: string) =>
    apiClient.put<UserInfo>('/user/profile', { name }),
}
