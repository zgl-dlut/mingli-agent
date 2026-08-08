/**
 * 支付 API
 */
import apiClient from './client'

export interface CreateOrderRequest {
  points: number
  pay_method: 'wechat' | 'alipay'
}

export interface OrderResponse {
  id: number
  points: number
  amount: number
  pay_method: string
  status: string
}

export interface Transaction {
  id: number
  type: string
  points: number
  description: string
  created_at: string
}

export const paymentApi = {
  createOrder: (data: CreateOrderRequest) =>
    apiClient.post<OrderResponse>('/payment/orders', data),

  getOrder: (id: number) =>
    apiClient.get<OrderResponse>(`/payment/orders/${id}`),

  getTransactions: () =>
    apiClient.get<Transaction[]>('/payment/transactions'),

  /** 创建微信支付订单 */
  createWechatOrder: (data: {
    points: number
    pay_type: 'jsapi' | 'h5'
    openid?: string
  }) => apiClient.post('/payment/create-wechat-order', data),

  /** 查询订单状态 */
  getOrderStatus: (orderId: string) =>
    apiClient.get(`/payment/order-status/${orderId}`),
}
