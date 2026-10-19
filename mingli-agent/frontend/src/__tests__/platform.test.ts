import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { isApp } from '../utils/platform'

describe('platform 端检测', () => {
  beforeEach(() => {
    sessionStorage.clear()
    delete window.__APP__
    window.history.replaceState({}, '', '/')
  })

  afterEach(() => {
    sessionStorage.clear()
    delete window.__APP__
    window.history.replaceState({}, '', '/')
  })

  it('URL 参数 ?app=1 覆盖为 App 端并写入会话缓存', () => {
    window.history.replaceState({}, '', '/?app=1')
    expect(isApp()).toBe(true)
    expect(sessionStorage.getItem('mingli_platform_app_override')).toBe('1')
  })

  it('URL 参数 ?app=0 覆盖为非 App 端，优先于原生注入标记', () => {
    window.__APP__ = true
    window.history.replaceState({}, '', '/?app=0')
    expect(isApp()).toBe(false)
  })

  it('会话内沿用缓存的覆盖值（URL 参数消失后仍生效）', () => {
    window.history.replaceState({}, '', '/?app=0')
    expect(isApp()).toBe(false)
    window.history.replaceState({}, '', '/today')
    expect(isApp()).toBe(false)
  })

  it('原生壳注入 window.__APP__ 时判定为 App 端', () => {
    window.__APP__ = true
    expect(isApp()).toBe(true)
  })

  it('无任何标记时回落到 vite 环境默认值（dev 视为 App，生产构建视为非 App）', () => {
    expect(isApp()).toBe(import.meta.env.DEV)
  })
})
