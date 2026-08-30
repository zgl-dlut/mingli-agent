import { useState, useEffect } from 'react'
import { adminApi } from '../api/admin'
import AdminNav from '../components/AdminNav'

const REVIEW_RESULT_OPTIONS = [
  { value: 'pass', label: '通过', color: 'bg-green-100 text-green-800' },
  { value: 'improve', label: '需改进', color: 'bg-yellow-100 text-yellow-800' },
  { value: 'fail', label: '不合格', color: 'bg-red-100 text-red-800' },
]

const PROBLEM_TAG_OPTIONS = ['跑题', '术语堆砌', '编造', '不通顺', '无依据', '括号标签式', '其他']

const RULE_CATEGORIES = ['术语', '结构', '命盘数据', '叙事性', '时间因果', '安全性']

const formatTime = (iso: string) => {
  const normalized = /Z|[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(normalized)
  if (isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function PromptReviewPage() {
  const [reviews, setReviews] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filterResult, setFilterResult] = useState<string>('')

  // 审核表单
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    user_question: '',
    review_result: 'fail',
    review_comment: '',
    problem_tags: [] as string[],
    auto_add_to_dataset: false,
  })
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState('')

  // LLM 规则提炼
  const [extracting, setExtracting] = useState<number | null>(null)
  const [ruleSuggestion, setRuleSuggestion] = useState('')
  const [ruleCategory, setRuleCategory] = useState('叙事性')

  const loadReviews = async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.promptReviews(
        filterResult ? { review_result: filterResult } : undefined
      )
      setReviews(data.items || [])
      setTotal(data.total || 0)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReviews()
  }, [filterResult])

  const handleSubmit = async () => {
    setSubmitting(true)
    setMessage('')
    try {
      await adminApi.submitPromptReview({
        user_question: form.user_question,
        review_result: form.review_result,
        review_comment: form.review_comment,
        problem_tags: form.problem_tags,
        auto_add_to_dataset: form.auto_add_to_dataset,
      })
      setMessage('审核提交成功')
      setShowForm(false)
      setForm({ user_question: '', review_result: 'fail', review_comment: '', problem_tags: [], auto_add_to_dataset: false })
      loadReviews()
    } catch (err: any) {
      setMessage('提交失败: ' + (err?.response?.data?.detail || '未知错误'))
    } finally {
      setSubmitting(false)
    }
  }

  const handleExtractRule = async (reviewId: number) => {
    setExtracting(reviewId)
    setRuleSuggestion('')
    try {
      const { data } = await adminApi.extractRule(reviewId)
      setRuleSuggestion(data.prompt || '')
    } catch (err: any) {
      setRuleSuggestion('提取失败: ' + (err?.response?.data?.detail || '未知错误'))
    } finally {
      setExtracting(null)
    }
  }

  const handleInjectPrompt = async (reviewId: number, rule: string) => {
    if (!rule.trim()) return
    try {
      await adminApi.injectPrompt(reviewId, {
        rule,
        rule_category: ruleCategory,
        confirm: true,
      })
      setMessage('规则已注入 prompt')
      loadReviews()
    } catch (err: any) {
      setMessage('注入失败: ' + (err?.response?.data?.detail || '未知错误'))
    }
  }

  const toggleTag = (tag: string) => {
    setForm((prev) => ({
      ...prev,
      problem_tags: prev.problem_tags.includes(tag)
        ? prev.problem_tags.filter((t) => t !== tag)
        : [...prev.problem_tags, tag],
    }))
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNav />
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* 头部 */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">人工审核</h1>
            <p className="text-sm text-gray-500 mt-1">
              审核生产报告质量，提炼规则并注入 prompt，形成优化闭环
            </p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            {showForm ? '收起表单' : '+ 新增审核'}
          </button>
        </div>

        {message && (
          <div className={`mb-4 px-4 py-3 rounded-lg text-sm ${message.includes('失败') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {message}
          </div>
        )}

        {/* 审核表单 */}
        {showForm && (
          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">新增人工审核</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">用户问题</label>
                <input
                  type="text"
                  value={form.user_question}
                  onChange={(e) => setForm({ ...form, user_question: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="输入用户问题（可选）"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">审核结果</label>
                <div className="flex gap-3">
                  {REVIEW_RESULT_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => setForm({ ...form, review_result: opt.value })}
                      className={`px-4 py-2 rounded-lg text-sm border ${
                        form.review_result === opt.value
                          ? `${opt.color} border-current`
                          : 'bg-gray-50 text-gray-500 border-gray-200'
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">问题标签</label>
                <div className="flex flex-wrap gap-2">
                  {PROBLEM_TAG_OPTIONS.map((tag) => (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      className={`px-3 py-1.5 rounded-lg text-sm border ${
                        form.problem_tags.includes(tag)
                          ? 'bg-blue-100 text-blue-700 border-blue-300'
                          : 'bg-gray-50 text-gray-500 border-gray-200'
                      }`}
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">审核意见</label>
                <textarea
                  value={form.review_comment}
                  onChange={(e) => setForm({ ...form, review_comment: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  rows={3}
                  placeholder="描述发现的问题..."
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="auto_add"
                  checked={form.auto_add_to_dataset}
                  onChange={(e) => setForm({ ...form, auto_add_to_dataset: e.target.checked })}
                  className="rounded"
                />
                <label htmlFor="auto_add" className="text-sm text-gray-700">
                  自动加入评测集（不合格 case 自动加入 eval_dataset.json）
                </label>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? '提交中...' : '提交审核'}
                </button>
                <button
                  onClick={() => setShowForm(false)}
                  className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200"
                >
                  取消
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 筛选 */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">筛选：</span>
            <button
              onClick={() => setFilterResult('')}
              className={`px-3 py-1.5 rounded-lg text-sm ${!filterResult ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}
            >
              全部 ({total})
            </button>
            {REVIEW_RESULT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setFilterResult(opt.value)}
                className={`px-3 py-1.5 rounded-lg text-sm ${filterResult === opt.value ? opt.color : 'bg-gray-100 text-gray-600'}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* 审核记录列表 */}
        {loading ? (
          <div className="text-center py-12 text-gray-500">加载中...</div>
        ) : reviews.length === 0 ? (
          <div className="text-center py-12 text-gray-500">暂无审核记录</div>
        ) : (
          <div className="space-y-4">
            {reviews.map((review) => (
              <div key={review.id} className="bg-white rounded-lg shadow p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-500">#{review.id}</span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      REVIEW_RESULT_OPTIONS.find((o) => o.value === review.review_result)?.color || 'bg-gray-100 text-gray-600'
                    }`}>
                      {REVIEW_RESULT_OPTIONS.find((o) => o.value === review.review_result)?.label || review.review_result}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400">{formatTime(review.created_at)}</span>
                </div>

                {review.user_question && (
                  <div className="mb-3">
                    <span className="text-xs text-gray-500">用户问题：</span>
                    <span className="text-sm text-gray-700">{review.user_question}</span>
                  </div>
                )}

                {review.problem_tags?.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-1">
                    {review.problem_tags.map((tag: string) => (
                      <span key={tag} className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}

                {review.review_comment && (
                  <div className="mb-3">
                    <span className="text-xs text-gray-500">审核意见：</span>
                    <span className="text-sm text-gray-700">{review.review_comment}</span>
                  </div>
                )}

                {review.auto_add_to_dataset === 1 && (
                  <div className="mb-3">
                    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">已加入评测集</span>
                  </div>
                )}

                {/* 操作按钮 */}
                {review.review_result === 'fail' && (
                  <div className="flex gap-2 pt-3 border-t border-gray-100">
                    <button
                      onClick={() => handleExtractRule(review.id)}
                      disabled={extracting === review.id}
                      className="px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded text-xs hover:bg-indigo-100 disabled:opacity-50"
                    >
                      {extracting === review.id ? '提取中...' : 'LLM 辅助提炼规则'}
                    </button>
                    {review.badcase_id && (
                      <span className="text-xs text-gray-400 self-center">
                        badcase #{review.badcase_id}
                      </span>
                    )}
                  </div>
                )}

                {/* 规则注入区域 */}
                {ruleSuggestion && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-gray-700">规则建议：</span>
                      <select
                        value={ruleCategory}
                        onChange={(e) => setRuleCategory(e.target.value)}
                        className="text-xs border border-gray-300 rounded px-2 py-1"
                      >
                        {RULE_CATEGORIES.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </div>
                    <textarea
                      value={ruleSuggestion}
                      onChange={(e) => setRuleSuggestion(e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2 text-sm mt-2"
                      rows={4}
                    />
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={() => handleInjectPrompt(review.id, ruleSuggestion)}
                        className="px-4 py-1.5 bg-green-600 text-white rounded text-xs hover:bg-green-700"
                      >
                        确认注入 prompt
                      </button>
                      <button
                        onClick={() => setRuleSuggestion('')}
                        className="px-4 py-1.5 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300"
                      >
                        取消
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
