/**
 * 命盘 API 契约测试
 *
 * 目的：把前后端约定的请求路径、参数名、柱位/等级枚举钉死在测试里，
 * 避免出现「字段名不一致 / 中英文混杂 / 等级多套叫法」这类问题。
 */
import { describe, it, expect, vi } from 'vitest'

vi.mock('../api/client', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: {} })) },
}))

import apiClient from '../api/client'
import { chartApi } from '../api/chart'
import { GRADE_LABEL } from '../api/daily'
import type { DailyGrade } from '../api/daily'
import type { PillarPosition } from '../api/chart'

const getMock = apiClient.get as unknown as ReturnType<typeof vi.fn>

describe('chartApi 契约', () => {
  it('① 请求路径为 /chart/{person_id}，参数名为 year + month', async () => {
    await chartApi.get(7, 2026, '2026-10')
    expect(getMock).toHaveBeenCalledWith('/chart/7', {
      params: { year: 2026, month: '2026-10' },
    })
  })

  it('② 省略 year/month 时不传参数（后端取当年当月）', async () => {
    await chartApi.get(7)
    expect(getMock).toHaveBeenCalledWith('/chart/7', { params: {} })
  })

  it('③ 柱位只有四个英文 token', () => {
    const positions: PillarPosition[] = ['year', 'month', 'day', 'hour']
    expect(positions).toHaveLength(4)
    for (const p of positions) {
      // 中文柱位禁止出现在传输层 token 中
      expect(p).toMatch(/^[a-z]+$/)
    }
  })

  it('④ 等级复用 daily 的三档英文 token，且无绝对化词', () => {
    const grades: DailyGrade[] = ['good', 'neutral', 'caution']
    expect(Object.keys(GRADE_LABEL).sort()).toEqual([...grades].sort())
    expect(Object.values(GRADE_LABEL).join('')).not.toMatch(/大吉|大凶/)
  })
})
