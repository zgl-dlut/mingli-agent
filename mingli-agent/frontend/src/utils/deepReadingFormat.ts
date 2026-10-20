/**
 * 深度解读大纲消息的解析工具
 *
 * 大纲消息 content 结构（与后端 chat.py / deep_reading.py 对齐）：
 * {"kind":"outline","question","verdict","subtopics":[{title,lead}],"detail":FollowupReport(可选，解锁后)}
 */

export interface OutlineItem {
  title: string
  lead: string
}

export interface OutlineReport {
  kind: 'outline'
  question: string
  verdict: string
  subtopics: OutlineItem[]
  /** 解锁后写入的完整正文；未解锁为 undefined */
  detail?: Record<string, unknown>
}

/** 解析大纲消息；非大纲返回 null */
export function parseOutlineReport(content: string): OutlineReport | null {
  if (!content || !content.trim().startsWith('{')) return null
  try {
    const data = JSON.parse(content)
    if (!data || data.kind !== 'outline') return null
    return {
      kind: 'outline',
      question: String(data.question || ''),
      verdict: String(data.verdict || ''),
      subtopics: Array.isArray(data.subtopics)
        ? data.subtopics
            .filter((it: unknown) => it && typeof it === 'object')
            .map((it: { title?: unknown; lead?: unknown }) => ({
              title: String(it.title || ''),
              lead: String(it.lead || ''),
            }))
        : [],
      detail: data.detail && typeof data.detail === 'object' ? data.detail : undefined,
    }
  } catch {
    return null
  }
}

export function isOutlineReport(content: string): boolean {
  return parseOutlineReport(content) !== null
}
