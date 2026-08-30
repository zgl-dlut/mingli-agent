import { useState, useEffect, useCallback } from 'react'
import { feedbackApi, FeedbackRecord, FeedbackStats, TagInfo } from '../api/feedback'
import AdminNav from '../components/AdminNav'

type ViewMode = 'list' | 'detail'

export default function FeedbackDashboard() {
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [tags, setTags] = useState<TagInfo[]>([])
  const [records, setRecords] = useState<FeedbackRecord[]>([])
  const [total, setTotal] = useState(0)
  const [selected, setSelected] = useState<FeedbackRecord | null>(null)
  const [view, setView] = useState<ViewMode>('list')

  // 筛选条件
  const [filterTag, setFilterTag] = useState<string>('')
  const [filterMinModel, setFilterMinModel] = useState<string>('')
  const [filterMaxModel, setFilterMaxModel] = useState<string>('')
  const [filterKeyword, setFilterKeyword] = useState<string>('')
  const [offset, setOffset] = useState(0)
  const limit = 20

  // 详情页人工打分
  const [humanScore, setHumanScore] = useState<number | ''>('')
  const [humanComment, setHumanComment] = useState('')
  const [saving, setSaving] = useState(false)

  const loadStats = useCallback(async () => {
    try {
      const data = await feedbackApi.stats()
      setStats(data)
    } catch (e) { console.error(e) }
  }, [])

  const loadTags = useCallback(async () => {
    try {
      const data = await feedbackApi.tags()
      setTags(data.tags || [])
    } catch (e) { console.error(e) }
  }, [])

  const loadList = useCallback(async () => {
    try {
      const data = await feedbackApi.list({
        tag: filterTag || undefined,
        min_model_score: filterMinModel ? Number(filterMinModel) : undefined,
        max_model_score: filterMaxModel ? Number(filterMaxModel) : undefined,
        keyword: filterKeyword || undefined,
        offset,
        limit,
      })
      setRecords(data.items || [])
      setTotal(data.total || 0)
    } catch (e) { console.error(e) }
  }, [filterTag, filterMinModel, filterMaxModel, filterKeyword, offset])

  useEffect(() => { loadStats(); loadTags(); loadList() }, [loadStats, loadTags, loadList])

  const refresh = () => { loadStats(); loadList() }

  const resetFilters = () => {
    setFilterTag('')
    setFilterMinModel('')
    setFilterMaxModel('')
    setFilterKeyword('')
    setOffset(0)
  }

  const openDetail = (record: FeedbackRecord) => {
    setSelected(record)
    setHumanScore(record.human_score ?? '')
    setHumanComment(record.human_comment ?? '')
    setView('detail')
  }

  const saveHumanScore = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await feedbackApi.updateScore(selected.id, {
        human_score: humanScore === '' ? null : Number(humanScore),
        human_comment: humanComment || null,
      })
      alert('保存成功')
      loadList()
      loadStats()
      // 更新本地记录
      setSelected({
        ...selected,
        human_score: humanScore === '' ? null : Number(humanScore),
        human_comment: humanComment,
      })
    } catch (e) {
      alert('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const triggerModelScore = async () => {
    if (!selected) return
    try {
      const result = await feedbackApi.triggerModelScore(selected.id)
      alert(`模型打分：${result.model_score}分\n理由：${result.reason}`)
      loadList()
      loadStats()
      setSelected({ ...selected, model_score: result.model_score, model_reason: result.reason })
    } catch (e) { alert('打分失败') }
  }

  const deleteRecord = async () => {
    if (!selected || !confirm('确定删除此记录？')) return
    try {
      await feedbackApi.remove(selected.id)
      alert('已删除')
      setView('list')
      setSelected(null)
      loadList()
      loadStats()
    } catch (e) { alert('删除失败') }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <AdminNav />
      {view === 'detail' && selected ? (
        <DetailView
          record={selected}
          humanScore={humanScore}
          setHumanScore={setHumanScore}
          humanComment={humanComment}
          setHumanComment={setHumanComment}
          saving={saving}
          onSave={saveHumanScore}
          onTriggerScore={triggerModelScore}
          onDelete={deleteRecord}
          onBack={() => { setView('list'); setSelected(null) }}
        />
      ) : (
        <ListView
          stats={stats}
          tags={tags}
          records={records}
          total={total}
          filterTag={filterTag}
          setFilterTag={(v) => { setFilterTag(v); setOffset(0) }}
          filterMinModel={filterMinModel}
          setFilterMinModel={(v) => { setFilterMinModel(v); setOffset(0) }}
          filterMaxModel={filterMaxModel}
          setFilterMaxModel={(v) => { setFilterMaxModel(v); setOffset(0) }}
          filterKeyword={filterKeyword}
          setFilterKeyword={(v) => { setFilterKeyword(v); setOffset(0) }}
          onReset={resetFilters}
          onRefresh={refresh}
          onSelect={openDetail}
          offset={offset}
          setOffset={setOffset}
          limit={limit}
        />
      )}
    </div>
  )
}

// ================ 列表视图 ================

function ListView(props: {
  stats: FeedbackStats | null
  tags: TagInfo[]
  records: FeedbackRecord[]
  total: number
  filterTag: string
  setFilterTag: (v: string) => void
  filterMinModel: string
  setFilterMinModel: (v: string) => void
  filterMaxModel: string
  setFilterMaxModel: (v: string) => void
  filterKeyword: string
  setFilterKeyword: (v: string) => void
  onReset: () => void
  onRefresh: () => void
  onSelect: (r: FeedbackRecord) => void
  offset: number
  setOffset: (n: number) => void
  limit: number
}) {
  const {
    stats, tags = [], records = [], total,
    filterTag, setFilterTag,
    filterMinModel, setFilterMinModel,
    filterMaxModel, setFilterMaxModel,
    filterKeyword, setFilterKeyword,
    onReset, onRefresh, onSelect,
    offset, setOffset, limit,
  } = props

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      {/* 头部 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">📊 反馈管理仪表盘</h1>
          <p className="text-sm text-slate-500 mt-1">
            标签统计 · 模型自评 · 人工打分 · Prompt 反哺
          </p>
        </div>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm"
        >
          🔄 刷新
        </button>
      </div>

      {/* 统计概览卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="总记录数" value={stats.total} color="blue" />
          <StatCard label="模型平均分" value={stats.avg_model_score || '—'} color="purple" />
          <StatCard label="人工平均分" value={stats.avg_human_score || '—'} color="green" />
          <StatCard label="已人工打分" value={`${stats.scored_count}/${stats.total}`} color="orange" />
        </div>
      )}

      {/* 标签统计 */}
      {stats && stats.tags && stats.tags.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6">
          <h2 className="text-base font-semibold text-slate-700 mb-3">🏷️ 标签分布</h2>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {stats.tags.map((t) => (
              <div key={t.tag} className="bg-slate-50 rounded-lg p-3 text-center">
                <div className="text-xs text-slate-500">{t.label}</div>
                <div className="text-lg font-bold text-slate-800 mt-1">{t.count}</div>
                <div className="text-xs text-slate-400 mt-1">
                  模型{t.avg_model_score}分 · 人工{t.avg_human_score}分
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 筛选器 */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-500 mb-1">标签</label>
            <select
              value={filterTag}
              onChange={(e) => setFilterTag(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value="">全部</option>
              {tags.map((t) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">模型分 ≥</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filterMinModel}
              onChange={(e) => setFilterMinModel(e.target.value)}
              placeholder="0-100"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">模型分 ≤</label>
            <input
              type="number"
              min={0}
              max={100}
              value={filterMaxModel}
              onChange={(e) => setFilterMaxModel(e.target.value)}
              placeholder="0-100"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">关键词</label>
            <input
              type="text"
              value={filterKeyword}
              onChange={(e) => setFilterKeyword(e.target.value)}
              placeholder="搜索问题/回答"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={onReset}
            className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 text-sm"
          >
            重置筛选
          </button>
        </div>
      </div>

      {/* 记录列表 */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="text-sm text-slate-600">
            共 <b className="text-slate-800">{total}</b> 条记录
          </span>
          <span className="text-xs text-slate-400">点击记录查看详情</span>
        </div>
        {records.length === 0 ? (
          <div className="py-16 text-center text-slate-400 text-sm">
            暂无反馈记录，使用命理解读后自动生成
          </div>
        ) : (
          <div className="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
            {records.map((r) => (
              <div
                key={r.id}
                onClick={() => onSelect(r)}
                className="px-4 py-3 hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <TagBadge tag={r.skill_tag} label={r.tag_label} />
                      {r.is_first_reading ? (
                        <span className="text-xs bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded">首次</span>
                      ) : (
                        <span className="text-xs bg-amber-100 text-amber-600 px-1.5 py-0.5 rounded">追问</span>
                      )}
                      <span className="text-xs text-slate-400">{r.created_at?.slice(0, 16).replace('T', ' ')}</span>
                    </div>
                    <div className="text-sm text-slate-800 truncate">{r.question}</div>
                    <div className="text-xs text-slate-500 mt-1 line-clamp-1">{r.answer_preview}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    {r.model_score != null && (
                      <ScorePill score={r.model_score} label="模型" color="purple" />
                    )}
                    {r.human_score != null && (
                      <ScorePill score={r.human_score} label="人工" color="green" />
                    )}
                    {r.model_score == null && (
                      <span className="text-xs text-slate-300">待打分</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 分页 */}
        {total > limit && (
          <div className="px-4 py-3 border-t border-slate-200 flex items-center justify-between">
            <span className="text-xs text-slate-400">
              显示 {offset + 1}-{Math.min(offset + limit, total)} / {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
                className="px-3 py-1 text-sm border border-slate-300 rounded disabled:opacity-40"
              >
                上一页
              </button>
              <button
                onClick={() => setOffset(offset + limit)}
                disabled={offset + limit >= total}
                className="px-3 py-1 text-sm border border-slate-300 rounded disabled:opacity-40"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ================ 详情视图 ================

function DetailView(props: {
  record: FeedbackRecord
  humanScore: number | ''
  setHumanScore: (v: number | '') => void
  humanComment: string
  setHumanComment: (v: string) => void
  saving: boolean
  onSave: () => void
  onTriggerScore: () => void
  onDelete: () => void
  onBack: () => void
}) {
  const { record, humanScore, setHumanScore, humanComment, setHumanComment, saving, onSave, onTriggerScore, onDelete, onBack } = props

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <button
        onClick={onBack}
        className="mb-4 text-sm text-blue-500 hover:text-blue-600"
      >
        ← 返回列表
      </button>

      {/* 问题和标签 */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <TagBadge tag={record.skill_tag} label={record.tag_label} />
          {record.is_first_reading ? (
            <span className="text-xs bg-blue-100 text-blue-600 px-2 py-0.5 rounded">首次解读</span>
          ) : (
            <span className="text-xs bg-amber-100 text-amber-600 px-2 py-0.5 rounded">追问</span>
          )}
          <span className="text-xs text-slate-400 ml-auto">{record.created_at?.slice(0, 16).replace('T', ' ')}</span>
        </div>
        <div className="text-base text-slate-800 font-medium">{record.question}</div>
      </div>

      {/* AI 回答 */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
        <h3 className="text-sm font-semibold text-slate-600 mb-2">🤖 AI 回答</h3>
        <div className="prose prose-sm max-w-none text-slate-700 whitespace-pre-wrap leading-relaxed">
          {record.answer}
        </div>
      </div>

      {/* 打分区 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        {/* 模型自评 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">🧠 模型自评</h3>
          {record.model_score != null ? (
            <>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-3xl font-bold text-purple-600">{record.model_score}</span>
                <span className="text-sm text-slate-400">/ 100</span>
              </div>
              <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded">
                {record.model_reason || '无打分理由'}
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-400 mb-3">尚未打分</div>
          )}
          <button
            onClick={onTriggerScore}
            className="mt-2 w-full px-3 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 text-sm"
          >
            {record.model_score != null ? '🔄 重新打分' : '✨ 模型打分'}
          </button>
        </div>

        {/* 人工打分 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">👤 人工打分</h3>
          <div className="flex items-center gap-3 mb-3">
            <input
              type="number"
              min={0}
              max={100}
              value={humanScore}
              onChange={(e) => setHumanScore(e.target.value === '' ? '' : Number(e.target.value))}
              placeholder="0-100"
              className="w-24 border border-slate-300 rounded-lg px-3 py-2 text-center text-lg font-bold"
            />
            <div className="flex gap-1">
              {[60, 70, 80, 90, 100].map((s) => (
                <button
                  key={s}
                  onClick={() => setHumanScore(s)}
                  className={`w-10 h-8 text-xs rounded ${humanScore === s ? 'bg-green-500 text-white' : 'bg-slate-100 text-slate-600'}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <textarea
            value={humanComment}
            onChange={(e) => setHumanComment(e.target.value)}
            placeholder="修改意见 / 补充说明（可选）"
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm h-20 resize-none"
          />
          <div className="flex gap-2 mt-3">
            <button
              onClick={onSave}
              disabled={saving}
              className="flex-1 px-3 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 text-sm disabled:opacity-50"
            >
              {saving ? '保存中...' : '💾 保存打分'}
            </button>
            <button
              onClick={onDelete}
              className="px-3 py-2 bg-red-100 text-red-600 rounded-lg hover:bg-red-200 text-sm"
            >
              🗑️ 删除
            </button>
          </div>
        </div>
      </div>

      {/* 反哺建议 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-amber-700 mb-2">💡 Prompt 反哺建议</h3>
        <p className="text-xs text-amber-600 leading-relaxed">
          {record.human_score != null && record.model_score != null && record.human_score < record.model_score
            ? `人工打分(${record.human_score})低于模型自评(${record.model_score})，说明回答可能存在表面正确但不够深入的问题。建议检查「${record.tag_label}」相关的 Prompt 模板，增加更多约束条件和具体案例。`
            : record.human_score != null && record.human_score >= 80
            ? `人工评分较高(${record.human_score}分)，当前「${record.tag_label}」Prompt 效果良好，可以作为正例参考。`
            : '请完成人工打分后，这里将显示 Prompt 优化建议。'}
        </p>
      </div>
    </div>
  )
}

// ================ 辅助组件 ================

function StatCard({ label, value, color }: { label: string; value: string | number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'text-blue-600',
    purple: 'text-purple-600',
    green: 'text-green-600',
    orange: 'text-orange-600',
  }
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${colors[color]}`}>{value}</div>
    </div>
  )
}

function TagBadge({ tag, label }: { tag: string; label: string }) {
  const tagColors: Record<string, string> = {
    career: 'bg-blue-100 text-blue-700',
    wealth: 'bg-yellow-100 text-yellow-700',
    marriage: 'bg-pink-100 text-pink-700',
    health: 'bg-green-100 text-green-700',
    fate: 'bg-purple-100 text-purple-700',
    general: 'bg-slate-100 text-slate-700',
  }
  const cls = tagColors[tag] || 'bg-slate-100 text-slate-700'
  return (
    <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>
      {label}
    </span>
  )
}

function ScorePill({ score, label, color }: { score: number; label: string; color: string }) {
  const colors: Record<string, string> = {
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    green: 'bg-green-50 text-green-700 border-green-200',
  }
  const cls = colors[color] || 'bg-slate-50 text-slate-700 border-slate-200'
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${cls}`}>
      {label} {score}分
    </span>
  )
}