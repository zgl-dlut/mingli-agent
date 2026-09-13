/**
 * 微信 JS-SDK 封装：按住说话 → 录音 → 语音转文字（仅微信内浏览器可用）
 *
 * 签名 URL 兼容（SPA 关键）：
 * - 安卓微信：签名用 wx.config 调用时的当前 URL
 * - iOS 微信：签名固定取"首次进入页面"的 URL（SPA 路由变化不更新）
 * 策略：先按当前 URL 签，wx.error 后回退首屏 URL 重签一次；config 成功后
 * JS 接口在同一文档内跨路由持续可用，无需重复 config。
 *
 * 接口清单依据官方文档：startRecord/stopRecord/onVoiceRecordEnd/translateVoice
 */
declare global {
  interface Window { wx?: any }
}

const WX_SDK_URL = 'https://res.wx.qq.com/open/js/jweixin-1.6.0.js'
// 模块加载即页面首屏（iOS 微信签名锚点）
const ENTRY_URL = window.location.href.split('#')[0]

let sdkPromise: Promise<any> | null = null
let configPromise: Promise<void> | null = null
let configDone = false

function loadSdk(): Promise<any> {
  if (window.wx) return Promise.resolve(window.wx)
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = WX_SDK_URL
      script.onload = () => resolve(window.wx)
      script.onerror = () => {
        sdkPromise = null
        reject(new Error('微信JS-SDK加载失败'))
      }
      document.head.appendChild(script)
    })
  }
  return sdkPromise
}

async function configOnce(url: string): Promise<void> {
  const wx = await loadSdk()
  const token = localStorage.getItem('mingli_token') || ''
  const res = await fetch(`/api/wechat/jssdk-sign?url=${encodeURIComponent(url)}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`签名获取失败(${res.status}) ${detail.slice(0, 80)}`)
  }
  const sign = await res.json()
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error('wx.config 超时')), 6000)
    wx.ready(() => {
      clearTimeout(timer)
      resolve()
    })
    wx.error((err: any) => {
      clearTimeout(timer)
      reject(new Error(err?.errMsg || 'wx.config 签名校验失败'))
    })
    wx.config({
      debug: false,
      appId: sign.appId,
      timestamp: sign.timestamp,
      nonceStr: sign.nonceStr,
      signature: sign.signature,
      jsApiList: ['startRecord', 'stopRecord', 'onVoiceRecordEnd', 'translateVoice'],
    })
  })
}

/** 确保微信 JS-SDK 已 config 成功（幂等）；失败后可重试 */
export async function ensureWxReady(): Promise<void> {
  if (configDone) return
  if (!configPromise) {
    const currentUrl = window.location.href.split('#')[0]
    configPromise = (async () => {
      try {
        await configOnce(currentUrl)
      } catch (e) {
        // iOS 微信 SPA 场景：回退用首屏 URL 重签
        if (currentUrl !== ENTRY_URL) {
          await configOnce(ENTRY_URL)
        } else {
          throw e
        }
      }
      configDone = true
    })()
    configPromise.catch(() => { configPromise = null })
  }
  return configPromise
}

/** 开始录音（需已 ensureWxReady；权限被拒会 reject 友好提示） */
export async function wxStartRecord(): Promise<void> {
  await ensureWxReady()
  const wx = await loadSdk()
  return new Promise((resolve, reject) => {
    wx.startRecord({
      success: () => resolve(),
      fail: (err: any) => {
        const msg = String(err?.errMsg || '')
        reject(new Error(msg.includes('auth') || msg.includes('deny') ? '请在微信设置中允许本页使用麦克风' : '录音启动失败，请重试'))
      },
      cancel: () => reject(new Error('录音已取消')),
    })
  })
}

/** 结束录音，返回 localId */
export async function wxStopRecord(): Promise<string> {
  await ensureWxReady()
  const wx = await loadSdk()
  return new Promise((resolve, reject) => {
    wx.stopRecord({
      success: (res: any) => resolve(res.localId as string),
      fail: () => reject(new Error('录音结束失败，请重试')),
    })
  })
}

/** 语音转文字：传录音 localId，返回识别文本 */
export async function wxTranslateVoice(localId: string): Promise<string> {
  await ensureWxReady()
  const wx = await loadSdk()
  return new Promise((resolve, reject) => {
    wx.translateVoice({
      localId,
      isShowProgressTips: 0,  // 用应用内弹窗展示加载态
      success: (res: any) => {
        const text = String(res.translateResult || '').trim()
        if (text) resolve(text)
        else reject(new Error('没听清，请靠近一点再说一次'))
      },
      fail: () => reject(new Error('语音识别失败，请重试')),
    })
  })
}

/** 注册"录音超过60秒自动结束"回调（等同用户松手，complete 返回 localId） */
export function wxOnRecordEnd(onComplete: () => void): void {
  loadSdk().then(wx => {
    wx.onVoiceRecordEnd({ complete: () => onComplete() })
  }).catch(() => { /* 非微信环境静默 */ })
}

/** 是否微信内浏览器（决定是否展示语音按钮） */
export function isWechatBrowser(): boolean {
  return /MicroMessenger/i.test(navigator.userAgent)
}
