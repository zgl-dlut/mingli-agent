/**
 * 微信浏览器检测与工具函数
 */

declare const WeixinJSBridge: any

/** 检测是否在微信内置浏览器中 */
export const isWechatBrowser = /MicroMessenger/i.test(navigator.userAgent)

/** 检测是否为 iOS 设备 */
export const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)

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
