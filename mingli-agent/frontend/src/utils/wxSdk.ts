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

/**
 * 在 wx.ready 回调内调用 JSSDK 接口。
 * 官方对 iOS 首次调用报 "the permission value is offline verifying" 的建议：
 * 接口必须在 ready 之后调用；自定义交互场景下 fail 后应在 ready 中重试。
 */
async function invokeWx<T = any>(api: string, params: Record<string, any> = {}): Promise<T> {
  await ensureWxReady()
  const wx = await loadSdk()
  return new Promise<T>((resolve, reject) => {
    wx.ready(() => {
      try {
        wx[api]({
          ...params,
          success: (res: any) => resolve(res),
          fail: (err: any) => reject(err),
          cancel: (err: any) => reject(err || { errMsg: `${api}:cancel` }),
        })
      } catch (e) {
        reject(e)
      }
    })
  })
}

const sleep = (ms: number) => new Promise(r => window.setTimeout(r, ms))

/**
 * 带自愈重试的接口调用：iOS 微信首次调用常返回 offline verifying
 * （权限值正在向微信服务器离线校验），等待后重试即可成功。
 */
async function invokeWxWithRetry<T>(
  api: string,
  params: Record<string, any>,
  retries = 2,
): Promise<T> {
  let lastErr: any
  for (let i = 0; i <= retries; i++) {
    try {
      return await invokeWx<T>(api, params)
    } catch (err: any) {
      lastErr = err
      const msg = String(err?.errMsg || err?.message || '')
      const isVerifying = msg.includes('offline verifying') || msg.includes('verify')
      // 非权限校验类错误（如用户拒绝授权）不重试
      if (!isVerifying && i > 0) throw err
      if (i < retries) await sleep(500)
    }
  }
  throw lastErr
}

/** config 是否已完成（同步读取；用于在用户手势中判断能否立即发起录音） */
export function isWxReadySync(): boolean {
  return configDone && !!window.wx
}

/**
 * 同步发起录音：必须在 pointerdown/touchstart 的【直接同步调用栈】中执行。
 * iOS 微信首次录音要弹系统麦克风授权，原生 bridge 只认用户触摸事件的同步
 * 调用栈——任何 await/setTimeout/wx.ready 回调都会让调用脱离手势，直接
 * 返回 startRecord:fail。Promise 的 executor 是同步执行的，所以返回 Promise
 * 只收结果、不延后发起。未 config 完成时 reject NOT_READY（不在内部等待，
 * 否则同样脱离手势），由调用方提示"再按一次"。
 */
export function wxStartRecordImmediate(): Promise<void> {
  const wx = window.wx
  if (!configDone || !wx) {
    // 未就绪：顺手触发/重试预热，本次不等待
    void ensureWxReady().catch(() => {})
    return Promise.reject(new Error('NOT_READY'))
  }
  return new Promise<void>((resolve, reject) => {
    try {
      wx.startRecord({
        success: () => resolve(),
        fail: (err: any) => reject(err),
        cancel: (err: any) => reject(err || { errMsg: 'startRecord:cancel' }),
      })
    } catch (e) {
      reject(e)
    }
  })
}

/**
 * 同步结束录音（同理须在 pointerup 手势栈内同步发起），Promise 收 localId。
 */
export function wxStopRecordImmediate(): Promise<string> {
  const wx = window.wx
  if (!configDone || !wx) return Promise.reject(new Error('NOT_READY'))
  return new Promise<string>((resolve, reject) => {
    try {
      wx.stopRecord({
        success: (res: any) => resolve(String(res.localId || '')),
        fail: (err: any) => reject(err),
        cancel: (err: any) => reject(err || { errMsg: 'stopRecord:cancel' }),
      })
    } catch (e) {
      reject(e)
    }
  })
}

/** 微信原始错误 → 用户可读提示 */
export function friendlyWxError(err: any): string {
  const msg = String(err?.errMsg || err?.message || '')
  if (msg === 'NOT_READY') {
    return '录音功能准备中，请再按一次'
  }
  if (msg.includes('auth') || msg.includes('deny') || msg.includes('permission')) {
    return '请允许微信使用麦克风后重试（手机设置→微信→麦克风）'
  }
  if (msg.includes('cancel')) {
    return ''
  }
  // 裸 startRecord:fail 多为手势栈脱离或系统权限问题，提示再按+检查系统权限
  return '录音启动失败，请再按一次；若多次失败，请到手机设置检查微信的麦克风权限'
}

/** 语音转文字：传录音 localId，返回识别文本 */
export async function wxTranslateVoice(localId: string): Promise<string> {
  const res = await invokeWxWithRetry<{ translateResult: string }>(
    'translateVoice',
    { localId, isShowProgressTips: 0 },  // 用应用内弹窗展示加载态
    2,
  )
  const text = String(res.translateResult || '').trim()
  if (text) return text
  throw new Error('没听清，请靠近一点再说一次')
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
