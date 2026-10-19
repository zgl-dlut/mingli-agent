/**
 * 端检测：App 端（原生壳 WebView）vs 浏览器直开（H5/PC）。
 *
 * 判定链（优先级从高到低）：
 * 1. URL 参数 ?app=1 / ?app=0 —— 显式覆盖，写入 sessionStorage 在会话内保持
 * 2. sessionStorage 中缓存的覆盖值
 * 3. 原生壳注入的全局标记 window.__APP__ === true
 * 4. vite dev 模式默认视为 App 端（本地联调方便）；生产构建默认非 App
 *
 * App 专属功能（今日 / 命盘等）仅在 isApp() 为 true 时展示入口并放行路由。
 */

declare global {
  interface Window {
    /** 原生壳启动 WebView 时注入：true 表示 App 端 */
    __APP__?: boolean
  }
}

const OVERRIDE_KEY = 'mingli_platform_app_override'

function readUrlOverride(): boolean | null {
  try {
    const v = new URLSearchParams(window.location.search).get('app')
    if (v === '1') return true
    if (v === '0') return false
  } catch {
    /* 非常规环境静默 */
  }
  return null
}

function readCachedOverride(): boolean | null {
  try {
    const v = sessionStorage.getItem(OVERRIDE_KEY)
    if (v === '1') return true
    if (v === '0') return false
  } catch {
    /* 隐私模式等静默 */
  }
  return null
}

export function isApp(): boolean {
  const urlOverride = readUrlOverride()
  if (urlOverride !== null) {
    try {
      sessionStorage.setItem(OVERRIDE_KEY, urlOverride ? '1' : '0')
    } catch {
      /* ignore */
    }
    return urlOverride
  }
  const cached = readCachedOverride()
  if (cached !== null) return cached
  if (window.__APP__ === true) return true
  return import.meta.env.DEV
}
