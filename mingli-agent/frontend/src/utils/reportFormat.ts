/**
 * 报告内容格式归一化器
 *
 * 设计目标：
 * 1. 统一入口：所有 LLM 输出的报告内容，先经过这里归一化，再交给 react-markdown 渲染。
 * 2. 关键词自识别：不依赖后端必须输出 `**关键词：**`，前端能自动把 "资金到账期：" 这类中文关键词识别并加粗。
 * 3. 块级拆分：一行内出现多个关键词块时，强制拆成独立段落，避免粘连。
 * 4. 与渲染解耦：本文件只负责把内容转换成"标准 Markdown"，不直接生成 HTML。
 *
 * 这样以后遇到新的关键词格式问题，只需要调整这一个文件里的规则，
 * 不需要再在前端渲染层堆叠正则。
 */

/** 可构成"关键词"的字符：中文、英文、数字、常见括号与连接符号 */
const KW_CHARS = '\\u4e00-\\u9fa5a-zA-Z0-9'
const KW_PUNCT = '（）()【】\\[\\]、·-'

/** 关键词结束符：半角冒号或全角冒号 */
const KW_COLON = '[：:]'

/** 非关键词开头：排除纯数字时间（如 12:30）、URL 协议等 */
const EXCLUDE_START = /^(\d{1,2}:\d{2}|https?|ftp|file|mailto)/

interface KeywordMatch {
  start: number
  end: number
  keyword: string
  colonIndex: number
}

/**
 * 判断一段文本是否看起来像"关键词"
 * - 长度 2-30
 * - 至少包含一个中文或英文字母
 * - 不以纯数字开头（避免匹配时间、编号）
 */
function looksLikeKeyword(text: string): boolean {
  if (text.length < 2 || text.length > 30) return false
  if (/^\d+$/.test(text)) return false
  if (!/[\u4e00-\u9fa5a-zA-Z]/.test(text)) return false
  return true
}

/**
 * 在一行文本中查找所有 "关键词：" 的位置
 * 使用正则迭代匹配，避免贪婪/非贪婪的边界问题
 */
function findKeywordMatches(line: string): KeywordMatch[] {
  const matches: KeywordMatch[] = []
  const regex = new RegExp(`([${KW_CHARS}${KW_PUNCT}]+?)${KW_COLON}`, 'g')
  let match: RegExpExecArray | null

  while ((match = regex.exec(line)) !== null) {
    const keyword = match[1]
    const start = match.index
    const end = regex.lastIndex

    if (looksLikeKeyword(keyword)) {
      matches.push({
        start,
        end,
        keyword,
        colonIndex: end - 1,
      })
    }
  }

  return matches
}

/**
 * 把一行内多个 "关键词：内容" 拆分成多行
 *
 * 例如：
 *   "资金到账期：8月。资金规划：稳健理财。"
 * 拆成：
 *   "资金到账期：8月。"
 *   "资金规划：稳健理财。"
 */
function splitKeywordLine(line: string): string[] {
  // 列表项不拆分（避免 - 前缀丢失，列表项内的关键词由 normalizeKeywordInLine 处理）
  if (line.trim().startsWith('-')) return [line]
  const matches = findKeywordMatches(line)
  if (matches.length <= 1) return [line]

  // 过滤掉已在 ** 加粗内部的关键词，避免拆断加粗结构导致 ** 错乱
  // 例如 "**关键词A：描述A** - 内容**关键词B：描述B**" 里的关键词都在加粗内，不应拆分
  const validMatches = matches.filter(m => {
    const before = line.slice(0, m.start)
    const after = line.slice(m.end)
    const boldOpenCount = (before.match(/\*\*/g) || []).length
    const boldCloseCount = (after.match(/\*\*/g) || []).length
    return !(boldOpenCount % 2 === 1 && boldCloseCount >= 1)
  })

  if (validMatches.length <= 1) return [line]

  const parts: string[] = []
  for (let i = 0; i < validMatches.length; i++) {
    const start = validMatches[i].start
    const end = i < validMatches.length - 1 ? validMatches[i + 1].start : line.length
    const part = line.slice(start, end).trim()
    if (part) parts.push(part)
  }

  // 保留关键词之前的引导语（如果存在且不是太长，且不含未配对的 **）
  const firstKw = validMatches[0]
  if (firstKw.start > 0) {
    const prefix = line.slice(0, firstKw.start).trim()
    const prefixBoldCount = (prefix.match(/\*\*/g) || []).length
    if (prefix && prefix.length <= 30 && prefixBoldCount % 2 === 0) {
      return [prefix, ...parts]
    }
  }

  return parts
}

/**
 * 修复行内 ** 加粗配对：如果 ** 数量为奇数，去掉最后一个未配对的 **
 * 兜底保护：即使其他环节产生未配对的 **，也能避免字面 ** 显示在页面上
 */
function fixBoldPairing(line: string): string {
  const count = (line.match(/\*\*/g) || []).length
  if (count % 2 === 0) return line
  // 奇数个 **，去掉最后一个未配对的
  const lastIdx = line.lastIndexOf('**')
  return line.slice(0, lastIdx) + line.slice(lastIdx + 2)
}

/**
 * 归一化行首关键词：把 `**关键词** 描述` 转成 `**关键词：**描述`
 * 只处理行首 **短语** 后接空格、且短语内不含冒号的情况
 * 用于修正追问报告中 LLM 漏掉冒号、用空格连接的格式
 * 不影响首次报告的 **关键词：描述**（整行加粗，正文另起一行）（短语内有冒号，不匹配）
 */
function normalizeLineStartKeyword(line: string): string {
  // 处理列表项：- **关键词** 描述 → - **关键词**：描述
  const listMatch = line.match(/^(-\s+)\*\*([^*]+)\*\*\s+(.+)/)
  if (listMatch) {
    const keyword = listMatch[2]
    if (/[：:]/.test(keyword)) return line
    return `${listMatch[1]}**${keyword}**：${listMatch[3]}`
  }
  // 处理普通行：**关键词** 描述 → **关键词**：描述
  const match = line.match(/^\*\*([^*]+)\*\*\s+(.+)/)
  if (!match) return line
  const keyword = match[1]
  // 短语内已有冒号则不处理（如首次报告的 **关键词：描述**（整行加粗，正文另起一行））
  if (/[：:]/.test(keyword)) return line
  // 转成 **关键词**：描述（冒号在加粗外，避免 react-markdown 嵌套 strong 解析错误）
  return `**${keyword}**：${match[2]}`
}

/**
 * 归一化列表项的关键词加粗格式（仅处理以 - 开头的列表项，不影响普通段落和首次报告）
 * - `- **关键词：描述**` → `- **关键词**：描述`（整体加粗改为只加粗关键词）
 * - `- **关键词：**描述` → `- **关键词**：描述`（冒号移到加粗外）
 * - `- **关键词**：描述` → 保持原样（已是正确格式）
 */
function normalizeListItem(line: string): string {
  const trimmed = line.trim()
  if (!trimmed.startsWith('-')) return line
  // 匹配 - **内容** 后续，用非贪婪避免一行多个加粗块时误匹配
  const match = trimmed.match(/^(-\s+)\*\*(.+?)\*\*\s*(.*)/)
  if (!match) return line
  const prefix = match[1]
  const boldContent = match[2]
  const rest = match[3]

  // 检查加粗内容中是否有冒号（关键词：描述 或 关键词：）
  const colonMatch = boldContent.match(/^([^：:]+)([：:])(.*)$/)
  if (!colonMatch) return line

  const keyword = colonMatch[1]
  const desc = colonMatch[3]

  // 重组：- **关键词**：描述 + rest
  if (rest) {
    return desc
      ? `${prefix}**${keyword}**：${desc} ${rest}`
      : `${prefix}**${keyword}**：${rest}`
  }
  return `${prefix}**${keyword}**：${desc}`
}

/**
 * 判断一行是否为"独占一行的短文本标题"
 * 条件：前后空行、长度<=15、不含段落标点、不以 # 或 ** 开头
 * 用于识别追问报告中 LLM 未加标记的分组小标题（如 家庭环境的"情绪稳定"）
 */
function isStandaloneTitle(lines: string[], index: number): boolean {
  const trimmed = lines[index].trim()
  if (!trimmed) return false
  // 已是标题或加粗，不处理
  if (trimmed.startsWith('#') || trimmed.startsWith('**')) return false
  // 列表项不处理
  if (trimmed.startsWith('-')) return false
  // 数字编号列表项不处理（如 "1. 小标题"），避免误加粗破坏有序列表
  if (/^\d+[.、)]/.test(trimmed)) return false
  // 长度限制（分组小标题通常 8-15 字）
  if (trimmed.length > 15) return false
  // 含段落级标点则不是标题
  if (/[。！？；，]/.test(trimmed)) return false
  // 前后必须是空行（或文件首尾）
  const prevLine = index > 0 ? lines[index - 1].trim() : ''
  const nextLine = index < lines.length - 1 ? lines[index + 1].trim() : ''
  if (prevLine !== '' || nextLine !== '') return false
  return true
}

/**
 * 把普通文本中的 "关键词：内容" 归一化为 "**关键词：** 内容"
 *
 * 规则：
 * 1. 不处理已用 ** 包裹的内容（避免重复加粗）
 * 2. 不处理 Markdown 标题行（# 开头）
 * 3. 不处理列表项内部已经处理过的关键词
 * 4. 关键词后至少要有内容才加粗（避免 "资金到账期：" 单独一行没有内容时仍加粗）
 */
function normalizeKeywordInLine(line: string): string {
  const trimmed = line.trim()
  if (!trimmed) return line
  if (trimmed.startsWith('#')) return line
  if (EXCLUDE_START.test(trimmed)) return line

  // 如果整行已经全是 markdown 加粗，不再处理
  if (/^\*\*.+\*\*$/.test(trimmed)) return line

  const matches = findKeywordMatches(trimmed)
  if (matches.length === 0) return line

  // 从后往前替换，避免索引偏移
  // 注意：每次替换后 result 长度会变化，因此后续替换必须在当前 result 上使用新的索引
  let result = trimmed
  for (let i = matches.length - 1; i >= 0; i--) {
    // 在最新 result 上重新查找所有关键词位置
    const currentMatches = findKeywordMatches(result)
    if (i >= currentMatches.length) continue

    const { start, end, keyword } = currentMatches[i]
    const afterColon = result.slice(end).trim()

    // 关键词后没有内容，保持原样（避免无意义加粗）
    if (!afterColon) continue

    // 检查该位置是否已在 **...** 内部
    const before = result.slice(0, start)
    const after = result.slice(end)
    const boldOpenCount = (before.match(/\*\*/g) || []).length
    const boldCloseCount = (after.match(/\*\*/g) || []).length
    const insideBold = boldOpenCount % 2 === 1 && boldCloseCount >= 1
    if (insideBold) {
      // 已在加粗内部
      if (after.startsWith('**')) {
        // ** 紧跟冒号（**关键词：**描述），把冒号移到加粗外，避免 react-markdown 嵌套 strong 解析错误
        const beforeColon = result.slice(0, end - 1)
        const afterBold = after.replace(/^\*\*\s*/, '')
        if (afterBold) {
          result = beforeColon + '**：' + afterBold
        }
      } else {
        // ** 不紧跟冒号（如首次报告 **关键词：描述**（整行加粗，正文另起一行）），只去掉 ** 与描述之间的空格
        const deSpaced = after.replace(/^(\*\*)\s+/, '$1')
        if (deSpaced !== after) {
          result = result.slice(0, end) + deSpaced
        }
      }
      continue
    }

    // 关键词后紧跟描述，冒号在加粗外（避免 react-markdown 嵌套 strong 解析错误）
    const replacement = `**${keyword}**：${afterColon}`
    result = result.slice(0, start) + replacement
  }

  return result
}

/**
 * 确保块级元素之间有适当的空行
 * - 标题行（# 开头）后面如果紧跟着非空行，插入一个空行
 * - 避免连续空行超过 2 个
 */
function ensureBlockSpacing(content: string): string {
  const lines = content.split('\n')
  const result: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()
    result.push(line)

    if (!trimmed) continue

    // 标题行后面需要跟一个空行
    const isHeading = trimmed.startsWith('#')
    if (isHeading) {
      // 如果下一行不是空行，则插入空行
      const nextLine = lines[i + 1]
      if (nextLine !== undefined && nextLine.trim() !== '') {
        result.push('')
      }
      continue
    }
  }

  // 合并连续空行，最多保留 2 个
  const compacted: string[] = []
  let emptyCount = 0
  for (const line of result) {
    if (line.trim() === '') {
      emptyCount++
      if (emptyCount <= 2) {
        compacted.push(line)
      }
    } else {
      emptyCount = 0
      compacted.push(line)
    }
  }

  return compacted.join('\n')
}

/**
 * 检测并移除连续重复的关键词段落。
 *
 * LLM 在长段落末尾偶尔会陷入"重复采样循环"——同一个以 `**关键词**` 开头的段落
 * 连续出现 2-3 次（最后一次常为截断版）。这里作为前端流式渲染时的兜底，
 * 保留首次出现的完整段落，移除后续重复项。
 *
 * 识别条件（同时满足才视为重复）：
 * 1. 当前行与上一个非空行之间只夹空行
 * 2. 两行都以 `**` 开头（避免误删总结里并列的列表项）
 * 3. 内容完全相同，或互为前缀且均长于 30 字符（处理截断重复）
 */
function dedupConsecutiveRepeats(content: string): string {
  const lines = content.split('\n')
  const result: string[] = []
  let lastNonEmptyContent: string | null = null

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      result.push(line)
      continue
    }

    let isDup = false
    if (lastNonEmptyContent !== null) {
      const prev: string = lastNonEmptyContent
      if (prev.startsWith('**') && trimmed.startsWith('**')) {
        if (prev === trimmed) {
          isDup = true
        } else if (trimmed.length > 30 && prev.length > 30) {
          if (prev.startsWith(trimmed) || trimmed.startsWith(prev)) {
            isDup = true
          }
        }
      }
    }

    if (isDup) {
      // 跳过当前重复行，并清理它前面累积的空行
      while (result.length > 0 && result[result.length - 1].trim() === '') {
        result.pop()
      }
      continue
    }

    result.push(line)
    lastNonEmptyContent = trimmed
  }

  return result.join('\n')
}

/**
 * 主入口：将报告内容归一化为标准 Markdown
 */
export function normalizeReportContent(content: string): string {
  if (!content || typeof content !== 'string') return ''

  // 统一换行符
  let normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

  // 移除超过 3 行的连续空行
  normalized = normalized.replace(/\n{4,}/g, '\n\n\n')

  // 去重连续重复段落（LLM 重复采样兜底，必须在关键词归一化之前执行）
  normalized = dedupConsecutiveRepeats(normalized)

  const lines = normalized.split('\n')
  const result: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 保留空行和标题行原样
    if (!trimmed) {
      result.push(line)
      continue
    }
    // 跳过孤立的 # 行（只有 # 没有内容，LLM 误用的分隔符）
    // 会被 react-markdown 渲染为空 <h2>，CSS 给 h2 加了底部边框，显示为横线
    if (/^#+\s*$/.test(trimmed)) {
      continue
    }
    if (trimmed.startsWith('#')) {
      result.push(line)
      continue
    }

    // 确保 ** 开头行之前有空行（防止段落合并）
    // LLM 在总结部分常输出 **战术一：...**。**战术二：...**。之间没有空行，
    // react-markdown 会把它们渲染为同一段
    if (trimmed.startsWith('**') && result.length > 0) {
      const prevTrimmed = result[result.length - 1].trim()
      if (prevTrimmed && !prevTrimmed.startsWith('#')) {
        result.push('')
      }
    }

    // 识别独占一行的短文本作为分组小标题并加粗（追问报告的分组标题）
    if (isStandaloneTitle(lines, i)) {
      result.push(`**${trimmed}**`)
      continue
    }

    // 列表项单独处理（避免 splitKeywordLine 拆分导致 - 前缀丢失）
    if (trimmed.startsWith('-')) {
      let normalizedList = normalizeListItem(trimmed)
      normalizedList = normalizeLineStartKeyword(normalizedList)
      normalizedList = normalizeKeywordInLine(normalizedList)
      result.push(fixBoldPairing(normalizedList))
      continue
    }

    // 拆分一行内多个关键词
    const splitLines = splitKeywordLine(trimmed)

    for (const part of splitLines) {
      // 归一化行首关键词：**关键词** 描述 → **关键词：**描述
      let normalizedPart = normalizeLineStartKeyword(part)
      normalizedPart = normalizeKeywordInLine(normalizedPart)
      // 兜底：确保 ** 加粗配对，避免未配对的 ** 字面显示
      result.push(fixBoldPairing(normalizedPart))
    }
  }

  normalized = result.join('\n')

  // 确保标题与后续段落之间有空行
  normalized = ensureBlockSpacing(normalized)

  return normalized
}

/**
 * 便捷函数：直接判断一行是否包含未被加粗的关键词（用于日志/调试）
 */
export function findUnboldedKeywords(content: string): string[] {
  const found: string[] = []
  const lines = content.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('#')) continue
    if (/^\*\*.+\*\*$/.test(trimmed)) continue

    const matches = findKeywordMatches(trimmed)
    for (const m of matches) {
      const before = trimmed.slice(0, m.start)
      const after = trimmed.slice(m.end)
      const boldOpenCount = (before.match(/\*\*/g) || []).length
      const boldCloseCount = (after.match(/\*\*/g) || []).length
      const insideBold = boldOpenCount % 2 === 1 && boldCloseCount >= 1
      if (!insideBold) {
        found.push(m.keyword)
      }
    }
  }
  return found
}
