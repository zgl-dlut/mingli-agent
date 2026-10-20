/**
 * 深度解读「分析框架」引导卡（对话流内）
 *
 * 用户在对话里提问后，后端（App 端 mode=outline）先只返回分析框架。
 * 该卡片向用户说明「本次深度解读会从多个维度展开」，并引导进入全屏深度解读页查看大纲、解锁正文。
 * 配色一律取自 src/theme/tokens。
 */
import { useNavigate } from 'react-router-dom'
import { color, gradient, radius, shadow } from '../theme/tokens'
import type { OutlineItem } from '../utils/deepReadingFormat'

interface OutlineCardProps {
  messageId: number
  verdict?: string
  subtopics?: OutlineItem[]
}

export default function OutlineCard({ messageId, verdict, subtopics = [] }: OutlineCardProps) {
  const navigate = useNavigate()
  const count = subtopics.length

  return (
    <div style={{ marginTop: '2px' }}>
      <div style={{ fontSize: '13px', color: color.ink, lineHeight: 1.7 }}>
        {verdict || '本次深度解读会从多个维度展开分析，你可以点击查看详情：'}
      </div>

      <button
        type="button"
        onClick={() => navigate(`/deep-reading/${messageId}`)}
        className="w-full flex items-center gap-3 text-left active:scale-[0.99] transition-transform"
        style={{
          marginTop: '10px',
          padding: '14px 16px',
          borderRadius: radius.card,
          background: gradient.unlock,
          border: `1px solid ${color.brandSoft}`,
          boxShadow: shadow.card,
        }}
      >
        {/* 深度解读图标 */}
        <span
          className="flex items-center justify-center flex-none"
          style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: color.card, color: color.brand, fontSize: '18px',
          }}
        >
          ✦
        </span>
        <span className="flex-1 min-w-0">
          <span style={{ display: 'block', fontSize: '14px', fontWeight: 700, color: color.ink }}>
            解锁专属深度解读
          </span>
          <span style={{ display: 'block', fontSize: '12px', color: color.ink2, marginTop: '2px' }}>
            {count > 0 ? `将从 ${count} 个维度展开 · 解读内容更详细` : '解读内容更详细'}
          </span>
        </span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: color.brand, flex: 'none' }}>
          开启分析 ›
        </span>
      </button>
    </div>
  )
}
