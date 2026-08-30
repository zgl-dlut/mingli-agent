/**
 * 支付 API
 */
import apiClient from './client'

export interface Transaction {
  id: number
  type: string
  points: number
  biz_type: string | null
  order_id: number | null
  description: string
  created_at: string
}

export interface CreateWechatOrderResponse {
  order_id: number
  points: number
  amount: number
  mock?: boolean
  pay_type?: string
  pay_params?: Record<string, any>
  h5_url?: string
  code_url?: string
}

export const paymentApi = {
  /** 创建微信支付订单（微信未配置时返回 mock: true） */
  createWechatOrder: (data: {
    points: number
    pay_type: 'jsapi' | 'native' | 'h5'
    openid?: string
  }) => apiClient.post<CreateWechatOrderResponse>('/payment/create-wechat-order', data),

  /** 查询订单状态 */
  getOrderStatus: (orderId: number) =>
    apiClient.get(`/payment/order-status/${orderId}`),

  /** 查询当前用户积分明细 */
  getTransactions: (limit: number = 100) =>
    apiClient.get<{ items: Transaction[] }>('/user/transactions', { params: { limit } }),
}
