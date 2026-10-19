/**
 * 前端领域模型
 *
 * 命名契约（单一事实来源）：
 * - 传输层字段一律由 `src/api/*.ts` 的接口定义，本文件不重复声明字段
 * - 本文件只做 re-export，保证前后端 + 前后端内部各层只有一套字段名
 * - 字段命名统一英文 snake_case；排盘数据 `bazi_data` 内部为中文键（历史遗留，冻结不改）
 */

import type { PersonResponse, CreatePersonRequest } from '../api/person'
import type { ChatMessage as ApiChatMessage, ChatSession as ApiChatSession } from '../api/chat'
import type { Transaction as ApiTransaction } from '../api/payment'

/** 人物：与后端 GET /api/persons 响应同构 */
export type Person = PersonResponse

/** 新建人物入参：与后端 POST /api/persons 请求同构 */
export type CreatePersonInput = CreatePersonRequest

/** 对话消息：与后端 GET /chat/sessions/{id}/messages 响应同构 */
export type ChatMessage = ApiChatMessage

/** 对话会话：与后端 GET /chat/sessions 响应同构 */
export type ChatSession = ApiChatSession

/** 积分流水：与后端 GET /user/transactions 响应同构 */
export type Transaction = ApiTransaction
