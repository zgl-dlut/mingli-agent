/**
 * 微信浏览器检测与工具函数
 */

declare const WeixinJSBridge: any

/** 检测是否在微信内置浏览器中 */
export const isWechatBrowser = /MicroMessenger/i.test(navigator.userAgent)

/** 检测是否为 iOS 设备 */
export const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)

/** 检测是否为移动端浏览器（非微信） */
export const isMobileBrowser = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)

/** 获取登录 token（全站统一 key：mingli_token，与 apiClient 一致） */
export function getAuthToken(): string | null {
  return localStorage.getItem('mingli_token')
}

/** 从当前 URL 获取查询参数 */
export function getUrlParam(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name)
}

/**
 * 调用微信 JSAPI 支付
 * @param payParams 后端返回的支付参数
 */
export function wxChooseWXPay(payParams: {
  appId: string
  timeStamp: string
  nonceStr: string
  package: string
  signType: string
  paySign: string
}): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof WeixinJSBridge === 'undefined') {
      reject(new Error('WeixinJSBridge 未就绪'))
      return
    }
    WeixinJSBridge.invoke(
      'getBrandWCPayRequest',
      {
        appId: payParams.appId,
        timeStamp: payParams.timeStamp,
        nonceStr: payParams.nonceStr,
        package: payParams.package,
        signType: payParams.signType,
        paySign: payParams.paySign,
      },
      (res: any) => {
        if (res.err_msg === 'get_brand_wcpay_request:ok') {
          resolve()
        } else if (res.err_msg === 'get_brand_wcpay_request:cancel') {
          reject(new Error('用户取消支付'))
        } else {
          reject(new Error(res.err_msg || '支付失败'))
        }
      }
    )
  })
}

/** 获取当前用户的微信 openid（后端已存储） */
export async function fetchMyOpenid(token: string): Promise<string | null> {
  try {
    const resp = await fetch('/api/auth/my-openid', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!resp.ok) return null
    const data = await resp.json()
    return data.openid || null
  } catch {
    return null
  }
}

/**
 * 确保微信内有 openid：先查后端存储，没有则跳转 OAuth 静默授权。
 * 跳转授权后页面会刷新，返回 null；已有时返回 openid。
 */
export async function ensureWechatOpenid(token: string): Promise<string | null> {
  const openid = await fetchMyOpenid(token)
  if (openid) return openid
  try {
    const resp = await fetch('/api/auth/wechat-oauth-url', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await resp.json()
    if (data.oauth_url) {
      window.location.href = data.oauth_url
      return null
    }
    console.error('[wechat] 获取 OAuth URL 失败:', data)
  } catch (err) {
    console.error('[wechat] 获取 OAuth URL 失败:', err)
  }
  return null
}
