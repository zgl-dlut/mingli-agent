/**
 * 管理后台 API
 */
import apiClient from './client'

export interface UsageLogItem {
  id: number
  user_id: number
  user_name: string
  session_id: number | null
  biz_type: string
  input_chars: number
  input_tokens: number
  output_chars: number
  output_tokens: number
  total_tokens: number
  cached_tokens: number
  model: string
  success: boolean
  duration_ms: number
  created_at: string
}

export interface OrderItem {
  id: number
  user_id: number
  user_name: string
  points: number
  amount: number
  pay_method: string
  status: string
  trade_no: string | null
  created_at: string
  paid_at: string | null
}

export interface EvalResultItem {
  id: number
  dataset_id: string
  eval_type?: string
  total: number
  passed: number
  failed: number
  pass_rate: number
  format_pass_rate: number | null
  match_count: number
  match_rate: number
  task_completion_rate?: {
    l1_technical: number
    l2_format: number
    l3_quality: number
    l4_satisfaction: number
    overall: number
  }
  accuracy_rate?: {
    chart: number
    structure: number
    narrative: number
    logic: number
    consistency: number
    safety: number
    overall: number
  }
  soft_score?: {
    narrative: number
    fluency: number
    storytelling: number
    bold_rationality: number
    terminology_popularization: number
    avg: number
  }
  violation_distribution?: Record<string, number>
  detail?: Array<{
    id: string
    description: string
    passed: boolean
    expected_pass: boolean
    match: boolean
    violations: Array<{
      type: string
      detail: string
    }>
    expected_violations: string[]
  }>
  created_at: string
}

export interface TrendPoint {
  version_id: number
  version_name: string
  value: number
  created_at: string
}

export interface EvalTypeInfo {
  type: string
  label: string
  description: string
  metrics: string[]
  count: number
  latest_time: string | null
}

export interface EvalCaseDetail {
  id: string
  description: string
  passed: boolean
  expected_pass: boolean
  match: boolean
  violations: Array<{
    type: string
    detail: string
  }>
  expected_violations: string[]
  report?: {
    opening?: {
      lead: string
      verdict: string
    }
    subtopics?: Array<{
      title: string
      blocks: Array<{
        keyword: string
        narrative: string
      }>
    }>
    summary?: {
      title: string
      items: Array<{
        keyword: string
        text: string
      }>
    }
  }
}

export interface EvalResultDetail extends EvalResultItem {
  detail: EvalCaseDetail[]
}

export interface FailureAnalysis {
  total_reports: number
  llm_evaluated: number
  passed: number
  failed: number
  pass_rate: number
  violation_distribution: Record<string, number>
  high_frequency_patterns: Array<{
    type: string
    count: number
    percentage: number
    examples: Array<{ id: number; question?: string; count?: number; score?: number; note?: string }>
  }>
  root_cause_distribution: Record<string, number>
  trigger_reason_distribution: Record<string, number>
  improvement_suggestions: Array<{
    priority: 'high' | 'medium' | 'low'
    category: string
    issue: string
    suggestion: string
    action_type: string
    examples?: Array<{ id: number; note?: string; question?: string }>
  }>
  analysis_period_days: number
}

export interface EvalCompareResult {
  baseline: {
    id: number
    dataset_id: string
    total: number
    passed: number
    failed: number
    pass_rate: number
    format_pass_rate: number
    task_completion_rate?: {
      l1_technical: number
      l2_format: number
      l3_quality: number
      l4_satisfaction: number
      overall: number
    }
    created_at: string
  }
  current: {
    id: number
    dataset_id: string
    total: number
    passed: number
    failed: number
    pass_rate: number
    format_pass_rate: number
    task_completion_rate?: {
      l1_technical: number
      l2_format: number
      l3_quality: number
      l4_satisfaction: number
      overall: number
    }
    created_at: string
  }
  delta: {
    pass_rate: number
    format_pass_rate: number
    passed_count: number
    l1_technical?: number
    l2_format?: number
    l3_quality?: number
    l4_satisfaction?: number
  }
  case_level: {
    improved: string[]
    regressed: string[]
    improved_count: number
    regressed_count: number
  }
  violation_distribution: Record<string, {
    baseline: number
    current: number
    delta: number
  }>
}

export const adminApi = {
  /** AI 用量记录 */
  usageLogs: (params: {
    offset?: number
    limit?: number
    biz_type?: string
    success?: boolean
    user_id?: number
  }) => apiClient.get<{ total: number; items: UsageLogItem[] }>('/admin/usage-logs', { params }),

  /** 充值订单记录 */
  orders: (params: {
    offset?: number
    limit?: number
    status?: string
    user_id?: number
  }) => apiClient.get<{ total: number; items: OrderItem[] }>('/admin/orders', { params }),

  /** 评测结果列表 */
  evalResults: (params?: {
    offset?: number
    limit?: number
    dataset_id?: string
    eval_type?: string
  }) => apiClient.get<{ total: number; items: EvalResultItem[] }>('/admin/eval-results', { params }),

  /** 评测结果详情 */
  evalResultDetail: (id: number) =>
    apiClient.get<EvalResultDetail>(`/admin/eval-results/${id}`),

  /** 评测结果对比 */
  evalCompare: (baseline_id: number, current_id: number) =>
    apiClient.get<EvalCompareResult>('/admin/eval-compare', { params: { baseline_id, current_id } }),

  /** 评测集内容 */
  evalDataset: () =>
    apiClient.get<{ total: number; items: any[] }>('/admin/eval-dataset'),

  /** 获取评测类型列表 */
  evalTypes: () =>
    apiClient.get<{ types: EvalTypeInfo[] }>('/admin/eval-types'),

  /** 获取指标趋势 */
  evalTrend: (params: {
    eval_type?: string
    metric_name?: string
    limit?: number
  }) => apiClient.get<{ metric_name: string; eval_type?: string; trend: TrendPoint[] }>('/admin/eval-trend', { params }),

  // ========== 人工审核 ==========

  /** 提交人工审核 */
  submitPromptReview: (data: {
    eval_result_id?: number
    badcase_id?: number
    report_data?: string
    user_question?: string
    reviewer_id?: number
    review_result: string
    review_comment?: string
    problem_tags?: string[]
    auto_add_to_dataset?: boolean
  }) => apiClient.post('/admin/prompt-review', data),

  /** 获取审核记录列表 */
  promptReviews: (params?: {
    review_result?: string
    offset?: number
    limit?: number
  }) => apiClient.get<{ total: number; items: any[] }>('/admin/prompt-reviews', { params }),

  /** LLM 辅助提炼规则 */
  extractRule: (review_id: number) =>
    apiClient.post(`/admin/prompt-review/${review_id}/extract-rule`),

  /** 确认规则并注入 prompt */
  injectPrompt: (review_id: number, data: { rule: string; rule_category: string; confirm: boolean }) =>
    apiClient.post(`/admin/prompt-review/${review_id}/inject-prompt`, data),

  /** 获取 prompt 版本历史 */
  promptVersions: (params?: { offset?: number; limit?: number }) =>
    apiClient.get<{ total: number; items: any[] }>('/admin/prompt-versions', { params }),

  /** 回滚 prompt 版本 */
  rollbackPromptVersion: (version_id: number) =>
    apiClient.post(`/admin/prompt-versions/${version_id}/rollback`, { confirm: true }),

  /** 添加用例到评测集 */
  addToEvalDataset: (data: {
    description: string
    user_question: string
    report_data?: string
    expected_pass: boolean
    expected_violations: string[]
    review_comment?: string
  }) => apiClient.post('/admin/eval-dataset/add', data),

  /** 管理员通过手机号充值积分 */
  rechargeByPhone: (data: { phone: string; points: number; remark?: string }) =>
    apiClient.post<{ user_id: number; user_name: string; phone: string; points_added: number; balance: number; order_id: number }>('/admin/recharge-by-phone', data),

  // ========== 问题归因与 Badcase 导出 ==========

  /** 更新评测结果的问题归因 */
  updateRootCause: (resultId: number, data: {
    category: 'prompt_issue' | 'code_bug' | 'rule_too_strict' | 'edge_case'
    note?: string
    fixed_in_version?: string
  }) => apiClient.put(`/admin/eval-results/${resultId}/root-cause`, data),

  /** 将生产监控未通过报告导出到评测集 */
  exportBadcase: (data: {
    eval_result_id: number
    description?: string
    expected_violations?: string[]
  }) => apiClient.post('/admin/eval-results/export-badcase', data),

  /** 失败模式分析：高频违规模式、归因分布与改进建议 */
  getFailureAnalysis: (days = 7, minOccurrences = 2) =>
    apiClient.get<FailureAnalysis>(`/admin/failure-analysis?days=${days}&min_occurrences=${minOccurrences}`),

  /** 分层人工复核：对 L1/L2/L3/LLM 评分标注认同或不认同 */
  updateLayerReview: (resultId: number, data: {
    layer: 'l1' | 'l2' | 'l3' | 'llm'
    verdict: 'agree' | 'disagree'
    note?: string
  }) => apiClient.put(`/admin/eval-results/${resultId}/layer-review`, data),
}
