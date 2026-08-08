/**
 * 全局诊断日志工具
 * 
 * 使用方法：
 *   import { createLogger } from '../utils/logger'
 *   const log = createLogger('ChatPage')
 *   log.info('handleSend 入口', { personId, question })
 * 
 * 输出格式（带颜色标记的 emoji 前缀）：
 *   [14:32:15.123] 📘 ChatPage | handleSend 入口 | {"personId":1,"question":"..."}
 * 
 * 级别：
 *   🔵 info     - 流程节点（入口、分支选择、关键变量）
 *   🟢 success  - 成功操作（消息写入、请求完成）
 *   🟡 warn     - 降级/非预期情况（mock fallback、去重拦截）
 *   🔴 error    - 异常/失败（网络错误、解析失败）
 *   ⚪ debug    - 详细数据（chunk 内容、时间戳）
 */

type LogLevel = 'info' | 'success' | 'warn' | 'error' | 'debug'

const EMOJI: Record<LogLevel, string> = {
  info: '🔵',
  success: '🟢',
  warn: '🟡',
  error: '🔴',
  debug: '⚪',
}

function timestamp(): string {
  const now = new Date()
  return now.toTimeString().slice(0, 8) + '.' + String(now.getMilliseconds()).padStart(3, '0')
}

function fmtData(data?: unknown): string {
  if (data === undefined) return ''
  if (typeof data === 'string') return ` | ${data}`
  try {
    return ` | ${JSON.stringify(data)}`
  } catch {
    return ` | ${String(data)}`
  }
}

export interface Logger {
  info: (msg: string, data?: unknown) => void
  success: (msg: string, data?: unknown) => void
  warn: (msg: string, data?: unknown) => void
  error: (msg: string, data?: unknown) => void
  debug: (msg: string, data?: unknown) => void
  callId: () => string
}

export function createLogger(module: string): Logger {
  const mod = `[${module}]`

  const log = (level: LogLevel, msg: string, data?: unknown) => {
    const prefix = `${EMOJI[level]} ${mod}`
    console.log(`[${timestamp()}] ${prefix} ${msg}${fmtData(data)}`)
  }

  return {
    info: (msg, data) => log('info', msg, data),
    success: (msg, data) => log('success', msg, data),
    warn: (msg, data) => log('warn', msg, data),
    error: (msg, data) => log('error', msg, data),
    debug: (msg, data) => log('debug', msg, data),
    callId: () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
  }
}

/** 生成一个唯一追踪ID，用于跟踪单次请求的完整生命周期 */
export function traceId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`
}
