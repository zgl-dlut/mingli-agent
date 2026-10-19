/**
 * 每日运势 API 契约测试
 *
 * 目的：把前后端约定的请求路径、参数名、grade 枚举钉死在测试里，
 * 避免出现「字段名不一致 / 中英文混杂 / 等级多套叫法」这类问题。
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: {} })) },
}))

import apiClient from '../api/client'
import { dailyApi, GRADE_LABEL } from '../api/daily'
import type { DailyGrade } from '../api/daily'

const getMock = apiClient.get as unknown as ReturnType<typeof vi.fn>

describe('dailyApi 契约', () => {
  it('① 请求路径为 /daily/fortune，参数名为 person_id + date', async () => {
    await dailyApi.fortune(7, '2026-10-14')
    expect(getMock).toHaveBeenCalledWith('/daily/fortune', {
      params: { person_id: 7, date: '2026-10-14' },
    })
  })

  it('② 省略 date 时只传 person_id（后端取服务器当日）', async () => {
    await dailyApi.fortune(7)
    expect(getMock).toHaveBeenCalledWith('/daily/fortune', { params: { person_id: 7 } })
  })

  it('③ grade 只允许三个英文 token，中文仅由展示层映射', () => {
    const grades: DailyGrade[] = ['good', 'neutral', 'caution']
    expect(Object.keys(GRADE_LABEL).sort()).toEqual([...grades].sort())
    expect(GRADE_LABEL.good).toBe('吉')
    expect(GRADE_LABEL.neutral).toBe('平')
    expect(GRADE_LABEL.caution).toBe('慎')
    // 禁止出现绝对化等级词
    expect(Object.values(GRADE_LABEL).join('')).not.toMatch(/大吉|大凶/)
  })
})
