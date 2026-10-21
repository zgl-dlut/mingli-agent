/**
 * 追问报告结构化渲染组件
 *
 * 接收后端返回的 JSON 字符串，解析后用 React 组件直接渲染（不走 Markdown 中间层）。
 * 格式 100% 由组件控制，不依赖 Markdown 解析，避免 `- ` 等语法模糊性。
 *
 * 内联加粗：文本字段里的 **加粗** 标记由 renderInline 解析为 <strong>。
 * 容器使用 report-content 类名，复用现有 CSS 样式（h2/p/strong/ul/li）。
 */
import React from 'react'
import { createLogger } from '../utils/logger'

const log = createLogger('FollowupReportView')

// ============================================================
// TypeScript 类型定义（对应后端 report_schema.py）
// ============================================================

interface Opening {
  lead?: string
  verdict?: string
}

interface KeywordBlock {
  type: 'keyword'
  keyword: string
  narrative: string
  sub_items?: string[]
}

interface NarrativeBlock {
  type: 'narrative'
  text: string
}

interface GroupBlock {
  type: 'group'
  title: string
  paragraphs: string[]
}

type Block = KeywordBlock | NarrativeBlock | GroupBlock

interface Subtopic {
  title: string
  lead?: string
  blocks: Block[]
  closing?: string
  /** 分析依据（本小节结论的命盘推演来源，LLM 输出，可展开展示） */
  basis?: string
}

interface SummaryItem {
  keyword: string
  text: string
}

interface Summary {
  title: string
  style_hint?: string
  lead?: string
  items?: SummaryItem[]
  item_format?: 'list' | 'paragraph'
  narrative?: string
  closing?: string
}

interface FollowupReportData {
  opening: Opening
  subtopics: Subtopic[]
  summary: Summary
}

// ============================================================
// renderInline：解析 **加粗** 和 \n\n 分段
// ============================================================

/** 解析 **加粗** 标记 + 处理 \n 换行，返回 React 节点数组 */
export function renderBold(text: string): React.ReactNode[] {
  if (!text) return []

  const parts = text.split(/\*\*([\s\S]+?)\*\*/g)
  const boldCount = Math.floor(parts.length / 2)
  const hasNewline = text.includes('\n')

  // 诊断日志：记录解析结果，便于排查加粗/换行渲染问题
  if (boldCount > 0 || hasNewline) {
    log.debug('renderBold 解析', {
      inputLength: text.length,
      boldCount,
      hasNewline,
      hasCrossLineBold: /\*\*[\s\S]*\n[\s\S]*\*\*/.test(text),
      partsCount: parts.length,
      preview: text.length > 80 ? text.slice(0, 80) + '...' : text,
    })
  }

  // 异常情况告警
  if (text.includes('***')) {
    log.warn('检测到连续三个*号，可能导致加粗匹配异常', { preview: text.slice(0, 60) })
  }

  return parts.map((part, i) => {
    if (i % 2 === 1) return <strong key={i}>{part}</strong>
    // 处理普通文本里的 \n（JSON.parse 后的换行符），渲染为 <br/>
    const lines = part.split('\n')
    if (lines.length <= 1) return <React.Fragment key={i}>{part}</React.Fragment>
    return lines.map((line, j) => (
      <React.Fragment key={`${i}-${j}`}>
        {j > 0 && <br />}
        {line}
      </React.Fragment>
    ))
  })
}

/** 渲染文本字段：支持 \n\n 分段 + **加粗** */
function renderInline(text: string): React.ReactNode {
  if (!text) return null
  // JSON.parse 后 \n\n 是真正的换行符
  const paragraphs = text.split('\n\n')
  if (paragraphs.length > 1) {
    log.debug('renderInline 分段渲染', { paragraphCount: paragraphs.length })
    return paragraphs.map((p, i) => <p key={i}>{renderBold(p)}</p>)
  }
  return <p>{renderBold(text)}</p>
}

// ============================================================
// 中文数字序号
// ============================================================

const CN_NUMS = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

// ============================================================
// 各部分渲染组件
// ============================================================

/** 开篇：lead + verdict */
function OpeningView({ data }: { data: Opening }) {
  return (
    <>
      {data.lead && renderInline(data.lead)}
      {data.verdict && renderInline(data.verdict)}
    </>
  )
}

/** 单个 block 渲染：根据 type 分发 */
function BlockView({ data }: { data: Block }) {
  if (data.type === 'keyword') {
    // 清洗 keyword 字段的 ** 号（LLM 偶尔输出，前端 <strong> 已加粗，不需要 **）
    const cleanKeyword = (data.keyword || '').replace(/\*\*/g, '').trim()
    return (
      <>
        <p>
          <span className="block-bullet">•</span> <strong>{cleanKeyword}</strong>{data.narrative && <>：{renderBold(data.narrative)}</>}
        </p>
        {data.sub_items && (
          <ul>
            {data.sub_items.map((item, i) => (
              <li key={i}>{renderBold(item)}</li>
            ))}
          </ul>
        )}
      </>
    )
  }
  if (data.type === 'narrative') {
    return <>{renderInline(data.text)}</>
  }
  // group
  return (
    <>
      <p><strong>{data.title}</strong></p>
      {data.paragraphs.map((p, i) => (
        <p key={i}>{renderBold(p)}</p>
      ))}
    </>
  )
}

/** 子问题：标题 + 可选引导段 + blocks + 可选总结句。标题保留中文序号 */
function SubtopicView({ data, index }: { data: Subtopic; index: number }) {
  const seq = CN_NUMS[index] || String(index + 1)
  return (
    <>
      <h2>{seq}、{data.title}</h2>
      {data.lead && renderInline(data.lead)}
      <div className="subtopic-blocks">
        {data.blocks.map((block, i) => (
          <BlockView key={i} data={block} />
        ))}
      </div>
      {data.closing && renderInline(data.closing)}
      {data.basis && (
        <details className="basis-toggle">
          <summary>分析依据</summary>
          <div className="basis-body">{renderBold(data.basis)}</div>
        </details>
      )}
    </>
  )
}

/** 总结：标题 + lead + items/narrative + closing */
function SummaryView({ data }: { data: Summary }) {
  const itemFormat = data.item_format || 'list'
  return (
    <>
      <h2>💡 {data.title}</h2>
      {data.lead && renderInline(data.lead)}
      {data.items && itemFormat === 'list' && (
        <ul>
          {data.items.filter(item => item.text && item.text.trim()).map((item, i) => (
            <li key={i}>
              <strong>{item.keyword}</strong>：{renderBold(item.text)}
            </li>
          ))}
        </ul>
      )}
      {data.items && itemFormat === 'paragraph' && (
        <>
          {data.items.filter(item => item.text && item.text.trim()).map((item, i) => (
            <p key={i}>
              <strong>{item.keyword}</strong>：{renderBold(item.text)}
            </p>
          ))}
        </>
      )}
      {data.narrative && renderInline(data.narrative)}
      {data.closing && renderInline(data.closing)}
    </>
  )
}

// ============================================================
// 主组件：解析 JSON 字符串，渲染完整报告
// ============================================================

export const FollowupReportView = React.memo(({ content }: { content: string }) => {
  let data: FollowupReportData | null = null
  try {
    data = JSON.parse(content)
  } catch (e) {
    log.error('FollowupReportView JSON解析失败', {
      error: String(e).slice(0, 100),
      contentLength: content.length,
      preview: content.slice(0, 80),
    })
    return null
  }
  if (!data || !data.opening || !data.subtopics || !data.summary) {
    log.warn('FollowupReportView 数据结构不完整', {
      hasOpening: !!data?.opening,
      hasSubtopics: !!data?.subtopics,
      hasSummary: !!data?.summary,
      subtopicCount: data?.subtopics?.length ?? 0,
    })
    return null
  }

  log.info('FollowupReportView 渲染报告', {
    subtopicCount: data.subtopics.length,
    contentLength: content.length,
  })

  return (
    <div className="report-content followup-report">
      <OpeningView data={data.opening} />
      {data.subtopics.map((sub, i) => (
        <SubtopicView key={i} data={sub} index={i} />
      ))}
      <SummaryView data={data.summary} />
    </div>
  )
})

/** 判断 content 是否为结构化 JSON 报告（用于 HtmlContent 分流渲染） */
export function isStructuredReport(content: string): boolean {
  if (!content || !content.trim().startsWith('{')) {
    return false
  }
  try {
    const parsed = JSON.parse(content)
    const hasFields = !!(parsed.opening && parsed.subtopics && parsed.summary)
    if (!hasFields) {
      log.warn('isStructuredReport JSON有效但缺少必要字段', {
        hasOpening: !!parsed.opening,
        hasSubtopics: !!parsed.subtopics,
        hasSummary: !!parsed.summary,
        topKeys: Object.keys(parsed),
      })
    }
    return hasFields
  } catch (e) {
    log.warn('isStructuredReport JSON解析失败，走Markdown渲染', {
      error: String(e).slice(0, 100),
      preview: content.slice(0, 60),
    })
    return false
  }
}
