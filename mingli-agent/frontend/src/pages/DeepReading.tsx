/**
 * AI 深度解读页（全屏，App 专属）
 *
 * 两段式咨询的第二段：用户从对话里的「解锁专属深度解读」卡进入。
 * 未解锁：展示分析框架大纲（可修改）+ 已选人物 + 解锁正文；
 * 解锁后：扣积分 → 「AI 深度分析中」→ 渲染完整正文 + 免责 + 反馈。
 *
 * 配色一律取自 src/theme/tokens（全站单一主色系）。
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { deepReadingApi } from '../api/deepReading'
import type { DeepReadingDetail, OutlineItem } from '../api/deepReading'
import { feedbackApi } from '../api/feedback'
import { FollowupReportView } from '../components/FollowupReportView'
import RechargeModal from '../components/RechargeModal'
import { useUserStore } from '../store/userStore'
import { color, gradient, radius, shadow } from '../theme/tokens'

/** 内容反馈标签（对齐测测：👍 弹正面组，👎 弹负面组） */
const POSITIVE_TAGS = ['逻辑清晰/易读懂', '专业性强，解读正确', '提供正向的情绪价值', '与事实接近']
const NEGATIVE_TAGS = ['内容主题不是我想要的', '读不懂/逻辑性差/有病句', '专业性知识错误', '内容影响心情']

export default function DeepReading() {
  const { messageId } = useParams<{ messageId: string }>()
  const navigate = useNavigate()
  const { fetchUserInfo } = useUserStore()
  const mid = Number(messageId)

  const [detail, setDetail] = useState<DeepReadingDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<OutlineItem[]>([])
  const [saving, setSaving] = useState(false)

  const [analyzing, setAnalyzing] = useState(false)
  const [showRecharge, setShowRecharge] = useState(false)

  const [voted, setVoted] = useState<'up' | 'down' | null>(null)
  const [showFeedback, setShowFeedback] = useState(false)
  // 反馈弹层的情感倾向：点赞/点踩打开时带入对应标签组；从「内容反馈」进入为 null（展示全部）
  const [fbSentiment, setFbSentiment] = useState<'up' | 'down' | null>(null)
  const [fbTags, setFbTags] = useState<string[]>([])
  const [fbText, setFbText] = useState('')
  const [fbDone, setFbDone] = useState(false)

  /** 点 👍/👎：记录倾向并弹出对应标签组的反馈层；再点已选中态则取消 */
  const handleVote = (v: 'up' | 'down') => {
    if (voted === v) { setVoted(null); return }
    setVoted(v)
    setFbSentiment(v)
    setFbTags([])
    setFbText('')
    setFbDone(false)
    setShowFeedback(true)
  }

  const openGenericFeedback = () => {
    setFbSentiment(voted)
    setFbTags([])
    setFbText('')
    setFbDone(false)
    setShowFeedback(true)
  }

  const load = useCallback(async () => {
    if (!mid) { setError('参数错误'); setLoading(false); return }
    setLoading(true)
    setError(null)
    try {
      const res = await deepReadingApi.get(mid)
      setDetail(res)
    } catch (e: unknown) {
      const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof d === 'string' ? d : '加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }, [mid])

  useEffect(() => { load() }, [load])

  const startEdit = () => {
    setDraft((detail?.subtopics || []).map((s) => ({ ...s })))
    setEditing(true)
  }

  const saveEdit = async () => {
    const cleaned = draft.filter((s) => s.title.trim())
    if (cleaned.length === 0) { alert('至少保留一个维度'); return }
    setSaving(true)
    try {
      const res = await deepReadingApi.updateOutline(mid, cleaned)
      setDetail(res)
      setEditing(false)
    } catch (e: unknown) {
      const d = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(typeof d === 'string' ? d : '保存失败，请稍后重试')
    } finally {
      setSaving(false)
    }
  }

  const handleUnlock = async () => {
    setAnalyzing(true)
    try {
      const res = await deepReadingApi.unlock(mid)
      setDetail(res)
      await fetchUserInfo()
    } catch (e: unknown) {
      const d = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const code = (d as { code?: string } | undefined)?.code
      if (code === 'insufficient_points') {
        setShowRecharge(true)
      } else {
        const msg = typeof d === 'string' ? d : (d as { message?: string } | undefined)?.message
        alert(msg || '解锁失败，请稍后重试')
      }
    } finally {
      setAnalyzing(false)
    }
  }

  const submitFeedback = async () => {
    if (fbTags.length === 0 && !fbText.trim()) { setShowFeedback(false); return }
    const sentimentLabel = fbSentiment === 'up' ? '正面' : fbSentiment === 'down' ? '负面' : '中性'
    try {
      await feedbackApi.create({
        question: '深度解读内容反馈',
        answer: `[${sentimentLabel}]${fbTags.length ? `[标签] ${fbTags.join('、')}` : ''}\n[补充] ${fbText.trim()}`,
        person_name: detail?.person_name || undefined,
        is_first_reading: false,
      })
    } catch {
      /* 反馈失败静默，不打断阅读 */
    }
    setFbDone(true)
    setShowFeedback(false)
  }

  const unlocked = !!detail?.unlocked && !!detail?.report

  // ── 分析中：全屏过渡 ──
  if (analyzing) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-8" style={{ backgroundColor: color.bg }}>
        <div style={{ width: '60%', height: '6px', borderRadius: radius.pill, backgroundColor: color.track, overflow: 'hidden' }}>
          <div className="ds-analyzing-bar" style={{ height: '100%', width: '40%', borderRadius: radius.pill, background: color.brand }} />
        </div>
        <div style={{ fontSize: '17px', fontWeight: 700, color: color.ink, marginTop: '20px' }}>
          AI 深度分析中
        </div>
        <div style={{ fontSize: '12px', color: color.ink2, marginTop: '8px', textAlign: 'center' }}>
          正在基于你的分析框架，调用命盘数据展开深度解读…
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen pb-28" style={{ backgroundColor: color.bg }}>
      {/* 顶栏 */}
      <div
        className="flex items-center"
        style={{ padding: '12px 12px', backgroundColor: color.bg, position: 'sticky', top: 0, zIndex: 10 }}
      >
        <button
          onClick={() => navigate(-1)}
          style={{ fontSize: '20px', color: color.ink, width: '28px', lineHeight: 1 }}
          aria-label="返回"
        >
          ‹
        </button>
        <div className="flex-1 text-center" style={{ fontSize: '17px', fontWeight: 700, color: color.ink }}>
          AI 深度解读
        </div>
        <span style={{ width: '28px' }} />
      </div>

      {loading && (
        <div className="text-center py-20" style={{ fontSize: '13px', color: color.ink2 }}>加载中…</div>
      )}

      {!loading && error && (
        <div className="text-center py-20">
          <p style={{ color: color.danger, fontSize: '13px' }} className="mb-3">{error}</p>
          <button
            onClick={load}
            className="rounded-full px-4 py-1.5"
            style={{ backgroundColor: color.brandSoft, color: color.brand, fontSize: '13px' }}
          >
            重试
          </button>
        </div>
      )}

      {/* 未解锁：分析框架大纲 */}
      {!loading && !error && detail && !unlocked && (
        <div className="px-4">
          <div style={{ fontSize: '20px', fontWeight: 800, color: color.ink, lineHeight: 1.5, margin: '4px 0 12px' }}>
            本次深度解读将从以下几个维度展开：
          </div>

          <div className="flex justify-between items-center" style={{ marginBottom: '10px' }}>
            <span
              className="inline-flex items-center gap-1"
              style={{ fontSize: '12px', color: color.ink2 }}
            >
              {detail.question ? `围绕「${detail.question.slice(0, 16)}${detail.question.length > 16 ? '…' : ''}」` : ''}
            </span>
            {!editing ? (
              <button
                onClick={startEdit}
                style={{ fontSize: '13px', fontWeight: 600, color: color.brand }}
              >
                ✎ 修改大纲
              </button>
            ) : (
              <span className="flex items-center gap-3">
                <button onClick={() => setEditing(false)} style={{ fontSize: '13px', color: color.ink2 }}>取消</button>
                <button
                  onClick={saveEdit}
                  disabled={saving}
                  style={{ fontSize: '13px', fontWeight: 600, color: color.brand, opacity: saving ? 0.5 : 1 }}
                >
                  {saving ? '保存中…' : '保存'}
                </button>
              </span>
            )}
          </div>

          <div
            style={{
              backgroundColor: color.card, borderRadius: radius.card, padding: '6px 16px',
              boxShadow: shadow.card,
            }}
          >
            {(editing ? draft : detail.subtopics).map((s, i) => (
              <div
                key={i}
                style={{
                  padding: '14px 0',
                  borderTop: i === 0 ? 'none' : `1px solid ${color.divider}`,
                }}
              >
                {editing ? (
                  <>
                    <input
                      value={s.title}
                      onChange={(e) => setDraft((d) => d.map((it, j) => (j === i ? { ...it, title: e.target.value } : it)))}
                      placeholder="维度标题"
                      style={{
                        width: '100%', fontSize: '15px', fontWeight: 700, color: color.ink,
                        padding: '8px 10px', borderRadius: '10px', border: `1px solid ${color.divider}`,
                        backgroundColor: color.bg, outline: 'none',
                      }}
                    />
                    <textarea
                      value={s.lead}
                      onChange={(e) => setDraft((d) => d.map((it, j) => (j === i ? { ...it, lead: e.target.value } : it)))}
                      placeholder="这一部分会分析…"
                      rows={2}
                      style={{
                        width: '100%', marginTop: '8px', fontSize: '13px', color: color.ink2, lineHeight: 1.6,
                        padding: '8px 10px', borderRadius: '10px', border: `1px solid ${color.divider}`,
                        backgroundColor: color.bg, outline: 'none', resize: 'none',
                      }}
                    />
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: color.ink, lineHeight: 1.6 }}>
                      {['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][i] || i + 1}、{s.title}
                    </div>
                    {s.lead && (
                      <div style={{ fontSize: '13px', color: color.ink2, lineHeight: 1.7, marginTop: '6px' }}>
                        {s.lead}
                      </div>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 已解锁：正文 */}
      {!loading && !error && unlocked && detail && detail.report && (
        <div className="px-4">
          <div
            style={{
              backgroundColor: color.card, borderRadius: radius.card, padding: '16px',
              boxShadow: shadow.card, marginTop: '4px',
            }}
          >
            <FollowupReportView content={JSON.stringify(detail.report)} />
          </div>

          {/* 文末免责 + 反馈 */}
          <div className="flex items-center justify-between" style={{ marginTop: '14px' }}>
            <span style={{ fontSize: '11px', color: color.ink2 }}>
              本解读基于AI生成，不作任何决策依据
            </span>
            <span className="flex items-center gap-3">
              <button
                onClick={() => handleVote('up')}
                style={{ fontSize: '16px', opacity: voted === 'down' ? 0.35 : 1 }}
                aria-label="有帮助"
              >
                👍
              </button>
              <button
                onClick={() => handleVote('down')}
                style={{ fontSize: '16px', opacity: voted === 'up' ? 0.35 : 1 }}
                aria-label="没帮助"
              >
                👎
              </button>
              <button
                onClick={openGenericFeedback}
                style={{ fontSize: '12px', color: color.ink2 }}
              >
                内容反馈
              </button>
            </span>
          </div>
        </div>
      )}

      {/* 底部固定：已选人物 + 解锁正文 */}
      {!loading && !error && detail && !unlocked && (
        <div
          className="fixed left-0 right-0 bottom-0"
          style={{ maxWidth: '430px', margin: '0 auto', padding: '10px 16px 16px', backgroundColor: color.bg }}
        >
          <div
            className="flex items-center justify-between"
            style={{
              backgroundColor: color.card, borderRadius: radius.card, padding: '12px 16px',
              boxShadow: shadow.card, marginBottom: '10px',
            }}
          >
            <span style={{ fontSize: '14px', color: color.ink2 }}>
              已选 <span style={{ color: color.ink, fontWeight: 600 }}>{detail.person_name || '本人'}</span>
            </span>
            <span style={{ fontSize: '16px', color: color.ink2 }}>›</span>
          </div>
          <button
            onClick={handleUnlock}
            className="w-full rounded-full py-3"
            style={{ background: gradient.yearHero, color: '#FFFFFF', fontSize: '16px', fontWeight: 700 }}
          >
            解锁正文 · {detail.unlock_points}积分
          </button>
        </div>
      )}

      {/* 充值弹窗（积分不足） */}
      <RechargeModal
        isOpen={showRecharge}
        onClose={() => setShowRecharge(false)}
        onRechargeSuccess={() => { setShowRecharge(false); fetchUserInfo() }}
      />

      {/* 内容反馈弹层 */}
      {showFeedback && (
        <div
          className="fixed inset-0 z-50 flex items-end"
          style={{ backgroundColor: 'rgba(43,43,51,0.35)', maxWidth: '430px', margin: '0 auto' }}
          onClick={() => setShowFeedback(false)}
        >
          <div
            className="w-full"
            style={{ backgroundColor: color.card, borderTopLeftRadius: '20px', borderTopRightRadius: '20px', padding: '20px 16px 24px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between" style={{ marginBottom: '14px' }}>
              <span style={{ fontSize: '16px', fontWeight: 700, color: color.ink }}>内容反馈</span>
              <button onClick={() => setShowFeedback(false)} style={{ fontSize: '18px', color: color.ink2 }}>×</button>
            </div>
            <div className="flex flex-wrap gap-2" style={{ marginBottom: '14px' }}>
              {(fbSentiment === 'up' ? POSITIVE_TAGS : fbSentiment === 'down' ? NEGATIVE_TAGS : [...POSITIVE_TAGS, ...NEGATIVE_TAGS]).map((t) => {
                const on = fbTags.includes(t)
                return (
                  <button
                    key={t}
                    onClick={() => setFbTags((prev) => (on ? prev.filter((x) => x !== t) : [...prev, t]))}
                    className="rounded-full"
                    style={{
                      fontSize: '12px', padding: '7px 12px',
                      color: on ? color.brand : color.ink2,
                      backgroundColor: on ? color.brandSoft : color.segBg,
                      border: `1px solid ${on ? color.brand : 'transparent'}`,
                    }}
                  >
                    {t}
                  </button>
                )
              })}
            </div>
            <textarea
              value={fbText}
              onChange={(e) => setFbText(e.target.value)}
              placeholder="留下你的反馈，我们会持续优化功能～"
              rows={3}
              style={{
                width: '100%', fontSize: '13px', color: color.ink, padding: '10px 12px',
                borderRadius: '12px', border: `1px solid ${color.divider}`, backgroundColor: color.bg,
                outline: 'none', resize: 'none',
              }}
            />
            <button
              onClick={submitFeedback}
              className="w-full rounded-full py-3"
              style={{ marginTop: '14px', backgroundColor: color.brand, color: '#FFFFFF', fontSize: '15px', fontWeight: 700 }}
            >
              提交反馈
            </button>
          </div>
        </div>
      )}

      {fbDone && (
        <div
          className="fixed left-1/2 bottom-24 rounded-full px-4 py-2 z-50"
          style={{ transform: 'translateX(-50%)', backgroundColor: 'rgba(43,43,51,0.86)', color: '#FFFFFF', fontSize: '13px' }}
        >
          感谢反馈
        </div>
      )}
    </div>
  )
}
