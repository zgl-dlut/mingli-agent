/**
 * EvalDashboard Mock 数据
 * 用于本地开发测试版本切换和指标趋势显示
 */

import type { EvalResultItem } from '../api/admin'

// 生成 5 个版本的 mock 数据
const generateMockVersions = (): EvalResultItem[] => {
  const baseDate = new Date('2026-08-13T10:00:00Z')
  
  return Array.from({ length: 5 }, (_, i) => {
    const id = 100 + i
    const date = new Date(baseDate.getTime() - i * 24 * 60 * 60 * 1000) // 每天一个版本
    
    // 模拟指标变化趋势
    const matchRate = 0.85 + i * 0.02 // 85% -> 93%
    const passRate = 0.70 + i * 0.03 // 70% -> 82%
    const formatPassRate = 0.90 + i * 0.01 // 90% -> 94%
    
    return {
      id,
      dataset_id: 'eval_dataset_v1',
      eval_type: i % 2 === 0 ? 'report_quality' : 'chart_accuracy',
      total: 50,
      passed: Math.floor(50 * passRate),
      failed: Math.floor(50 * (1 - passRate)),
      pass_rate: passRate,
      format_pass_rate: formatPassRate,
      match_count: Math.floor(50 * matchRate),
      match_rate: matchRate,
      task_completion_rate: {
        l1_technical: 0.95,
        l2_format: formatPassRate,
        l3_quality: 0.88,
        l4_satisfaction: 0.82,
        overall: 0.85 + i * 0.015,
      },
      accuracy_rate: {
        chart: 0.92 + i * 0.01,
        structure: 0.88 + i * 0.02,
        narrative: 0.85 + i * 0.015,
        logic: 0.90 + i * 0.01,
        consistency: 0.87 + i * 0.02,
        safety: 0.95,
        overall: 0.89 + i * 0.015,
      },
      soft_score: {
        narrative: 4.2 + i * 0.1,
        fluency: 4.5 + i * 0.05,
        storytelling: 4.0 + i * 0.15,
        bold_rationality: 4.3 + i * 0.1,
        terminology_popularization: 4.1 + i * 0.12,
        avg: 4.2 + i * 0.1,
      },
      violation_distribution: {
        '术语黑名单': 3 - i,
        '时间节点冲突': 2 - Math.floor(i / 2),
        '结论矛盾': 1,
      },
      detail: [
        {
          id: 'case_001',
          description: '测试用例1：换工作时机',
          passed: true,
          expected_pass: true,
          match: true,
          violations: [],
          expected_violations: [],
        },
        {
          id: 'case_002',
          description: '测试用例2：感情复合概率',
          passed: false,
          expected_pass: false,
          match: true,
          violations: [
            {
              type: '术语黑名单',
              detail: '使用了"七杀"术语，应替换为大白话',
            },
          ],
          expected_violations: ['术语黑名单'],
        },
      ],
      created_at: date.toISOString(),
    }
  })
}

export const mockEvalResults = generateMockVersions()

// Mock API 响应
export const mockApi = {
  evalResults: async (params?: {
    offset?: number
    limit?: number
    dataset_id?: string
    eval_type?: string
  }) => {
    console.log('[Mock API] evalResults called', params)
    
    let filtered = [...mockEvalResults]
    
    // 按评测类型筛选
    if (params?.eval_type) {
      filtered = filtered.filter(item => item.eval_type === params.eval_type)
    }
    
    // 按评测集ID筛选
    if (params?.dataset_id) {
      filtered = filtered.filter(item => item.dataset_id === params.dataset_id)
    }
    
    // 分页
    const offset = params?.offset || 0
    const limit = params?.limit || 20
    const paginated = filtered.slice(offset, offset + limit)
    
    return {
      data: {
        total: filtered.length,
        items: paginated,
      },
    }
  },
  
  evalResultDetail: async (id: number) => {
    console.log('[Mock API] evalResultDetail called', { id })
    
    const item = mockEvalResults.find(r => r.id === id)
    if (!item) {
      throw new Error(`Version ${id} not found`)
    }
    
    return { data: item }
  },
  
  evalDataset: async () => {
    console.log('[Mock API] evalDataset called')
    
    return {
      data: {
        total: 2,
        items: [
          {
            id: 'case_001',
            description: '测试用例1：换工作时机',
            user_question: '什么时候换工作最好？',
            expected_pass: true,
            check_points: ['时间窗口合理性', '命理依据充分'],
          },
          {
            id: 'case_002',
            description: '测试用例2：感情复合概率',
            user_question: '和前任还能复合吗？',
            expected_pass: false,
            check_points: ['避免绝对化表述', '术语通俗化'],
          },
        ],
      },
    }
  },
}
