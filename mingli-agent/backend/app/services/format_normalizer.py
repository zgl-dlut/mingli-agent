"""
格式归一化模块 (Format Normalizer)

在LLM输出后、前端渲染前，程序化地确保格式合规。
替代前端大量正则修补逻辑，从根本上解决格式不稳定问题。

核心功能：
1. 结构化解析：将输出拆分为标题、段落、列表、总结等结构块
2. 关键词自动加粗：检测"关键词：内容"模式并自动包裹格式
3. 标题层级校验：确保标题格式正确
4. 列表格式统一：规范化列表格式
5. 违规内容检测：检查是否有违规内容（如"核心结论"）

使用方式：
    from app.services.format_normalizer import normalize_output
    normalized = normalize_output(llm_output)
"""

import re
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构定义
# ============================================================

class Block:
    """内容块基类"""
    def __init__(self, content: str):
        self.content = content

class HeadingBlock(Block):
    """标题块"""
    def __init__(self, content: str, level: int = 2):
        super().__init__(content)
        self.level = level  # 2=##, 3=###

class ParagraphBlock(Block):
    """段落块"""
    pass

class ListBlock(Block):
    """列表块"""
    def __init__(self, items: List[str], ordered: bool = False):
        self.items = items
        self.ordered = ordered

class SummaryBlock(Block):
    """总结块"""
    def __init__(self, content: str, title: str = ""):
        super().__init__(content)
        self.title = title

class KeywordLine:
    """关键词行（关键词：内容）"""
    def __init__(self, keyword: str, description: str, with_bold: bool = False):
        self.keyword = keyword
        self.description = description
        self.with_bold = with_bold  # 是否已用**包裹


# ============================================================
# 主入口：normalize_output
# ============================================================

def normalize_output(content: str, preserve_h3: bool = False) -> str:
    """
    对LLM输出进行格式归一化。

    处理流程：
    1. 解析结构块
    2. 规范化每个块的格式
    3. 检测并修复违规内容
    4. 返回规范化后的文本

    Args:
        content: LLM原始输出

    Returns:
        规范化后的文本
    """
    if not content or not content.strip():
        return content

    # 步骤0：移除【】方括号（已弃用的关键词标记格式，字符串替换非正则，最健壮）
    content = content.replace('【', '').replace('】', '')

    # 步骤1：清理异常空白和控制字符
    content = _clean_content(content)

    # 步骤1.5：去重连续重复段落（LLM在长段落末尾陷入重复采样循环时的兜底）
    #   例：同一关键词段"**职场权力稳固期**：..." 连续出现2-3次（最后一次常截断）
    #   必须在关键词归一化之前执行，避免重复段干扰后续格式处理
    content = _dedup_consecutive_repeats(content)

    # 步骤2：检测并修复常见违规
    content = _fix_violations(content)

    # 步骤3：规范化标题格式
    content = _normalize_headings(content, preserve_h3=preserve_h3)

    # 步骤4：规范化关键词加粗
    content = _normalize_keywords(content)

    # 步骤5：规范化列表格式
    content = _normalize_lists(content)

    # 步骤6：规范化总结部分
    content = _normalize_summary(content)

    # 步骤7：移除残留的无效标记
    content = _cleanup_residuals(content)

    # 步骤7.5：格式检测与自动修正
    #   规则1：每个子问题下至少一个段落开头加黑，没有则自我修正
    #   规则2：段落开头出现残破 **（加粗失败）则修正后再输出
    content = _ensure_keyword_coverage(content)

    # 步骤8：确保标题与后续段落之间有空行
    content = _ensure_heading_spacing(content)

    logger.info("[FormatNormalizer] 格式归一化完成")
    return content


def _ensure_heading_spacing(content: str) -> str:
    """确保标题行与后续非空行之间有一个空行"""
    lines = content.split('\n')
    result = []
    for i, line in enumerate(lines):
        result.append(line)
        stripped = line.strip()
        if stripped.startswith('#') and i + 1 < len(lines) and lines[i + 1].strip():
            result.append('')
    return '\n'.join(result)


# ============================================================
# 各处理步骤实现
# ============================================================

def _clean_content(content: str) -> str:
    """清理异常空白和控制字符"""
    # 统一换行符
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # 移除多余空行（超过3个连续空行压缩为2个）
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    # 移除行首行尾空白
    lines = [line.rstrip() for line in content.split('\n')]

    return '\n'.join(lines)


def _dedup_consecutive_repeats(content: str) -> str:
    """检测并移除连续重复的关键词段落。

    LLM 在长段落末尾偶尔会陷入"重复采样循环"——同一个以 `**关键词**` 开头的段落
    连续出现 2-3 次（最后一次常为截断版）。这里作为兜底，保留首次出现的完整段落，
    移除后续重复项。

    识别条件（同时满足才视为重复）：
    1. 当前行与上一个非空行之间只夹空行（中间无其他实质内容隔开）
    2. 两行都以 `**` 开头（关键词段落，避免误删总结里并列的列表项）
    3. 内容完全相同，或互为前缀且均长于 30 字符（处理截断重复）
    """
    lines = content.split('\n')
    result: List[str] = []
    last_non_empty_content: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        is_dup = False
        if last_non_empty_content is not None:
            prev = last_non_empty_content
            # 仅处理都以 ** 开头的关键词段落，避免误删合法并列结构
            if prev.startswith('**') and stripped.startswith('**'):
                if prev == stripped:
                    is_dup = True
                elif len(stripped) > 30 and len(prev) > 30:
                    # 截断重复：一行是另一行的前缀
                    if prev.startswith(stripped) or stripped.startswith(prev):
                        is_dup = True

        if is_dup:
            # 跳过当前重复行，并清理它前面累积的空行
            # （后续 _ensure_heading_spacing / _cleanup_residuals 会补回必要空行）
            while result and result[-1].strip() == '':
                result.pop()
            continue

        result.append(line)
        last_non_empty_content = stripped

    return '\n'.join(result)


def _fix_violations(content: str) -> str:
    """检测并修复违规内容"""
    violations_fixed = 0

    # 0. 预处理：将子问题内部的 "### 核心结论：" / "**核心结论：**" 等
    #    替换为允许的 "关键判断"，避免后续移除时残留无意义符号
    content = re.sub(r'(?<![#\*])\*\*核心结论\*\*[：:]', '**关键判断：**', content)
    content = re.sub(r'(?<!#)###\s*核心结论[：:]', '### 关键判断：', content)

    # 1. 移除子问题内部的"核心结论"字样（严禁在子问题内部使用）
    # 保留一级标题中的核心结论
    lines = content.split('\n')
    result_lines = []
    for i, line in enumerate(lines):
        # 如果该行包含"核心结论"但不是一级标题（## 开头），则移除"核心结论"字样
        if '核心结论' in line and not line.strip().startswith('## '):
            line = line.replace('核心结论：', '').replace('核心结论:', '')
            line = line.replace('**核心结论**', '').replace('核心结论', '')
            # 清理可能残留的空冒号或多余星号
            line = re.sub(r'\*\*\s*[：:]\s*', '**关键判断：** ', line)
            line = line.strip()
            if line.strip():  # 确保移除后该行不为空
                result_lines.append(line)
            violations_fixed += 1
        else:
            result_lines.append(line)

    content = '\n'.join(result_lines)

    # 2. 移除总结部分的"总结"二字（保留## 💡 标题格式）
    # 匹配"总结："、"总结如下"、"最后总结"等字样
    # 但保留"总结"出现在标题中的情况（如"## 💡 求职总结"）
    lines = content.split('\n')
    result_lines = []
    for line in lines:
        stripped = line.strip()
        # 如果该行不是标题行（不以#开头），则移除"总结"相关字样
        if not stripped.startswith('#'):
            line = re.sub(r'总结如下[：:]?\s*', '', line)
            line = re.sub(r'最后总结[：:]?\s*', '', line)
            # 移除行首的"总结："（不影响正文中间的"总结"二字）
            line = re.sub(r'^总结[：:]\s*', '', line)
        result_lines.append(line)
    content = '\n'.join(result_lines)

    if violations_fixed > 0:
        logger.info(f"[FormatNormalizer] 修复了 {violations_fixed} 处违规内容")

    return content


def _normalize_headings(content: str, preserve_h3: bool = False) -> str:
    """规范化标题格式"""
    # 先处理内联的 "### 关键词：描述"，避免其被当作普通文本保留
    # 例如："...关键。### 核心结论：精准出击" → "...关键。\n\n**关键判断：** 精准出击"
    if not preserve_h3:
        content = re.sub(
            r'(?<!\n)###\s+([^#\n]{2,30}[：:])([^#\n]*)',
            r'\n\n**\1**\2',
            content,
        )

    lines = content.split('\n')
    result = []
    heading_index = 0  # 子问题序号计数器（用于自动补全中文数字序号）

    for line in lines:
        stripped = line.strip()

        # 处理 ### 标题（二级标题，可能是关键词标题）
        # 注意：必须先判断 ###，因为 ### 也满足 ## 的前缀条件
        if stripped.startswith('### '):
            if preserve_h3:
                # 首次报告模式：保留 ### 标题（前端渲染为 h3，有视觉区分）
                result.append(stripped)
            else:
                # 追问模式：转换为关键词加粗格式
                stripped = re.sub(r'^###\s*', '', stripped)
                # 如果是"关键词：描述"格式，转换为加粗（冒号在加粗外，统一格式）
                match = re.match(r'^([^\s：:]+[：:])\s*(.*)', stripped)
                if match:
                    keyword = match.group(1).rstrip('：:')
                    description = match.group(2)
                    stripped = f'**{keyword}**：{description}'
                result.append(stripped)

        # 处理 ## 标题（一级段落标题）
        elif stripped.startswith('## '):
            # 移除多余的#号（如 #### 降级为 ##）
            stripped = re.sub(r'^#{2,}\s*', '## ', stripped)
            # 自动补全中文数字序号（总结部分不加序号）
            title_content = stripped[3:].strip()  # 移除 "## " 前缀
            is_summary = title_content.startswith('💡') or title_content.startswith('总结')
            has_seq = bool(re.match(r'^[一二三四五六七八九十]+、', title_content))
            if not is_summary and not has_seq:
                seq_chars = '一二三四五六七八九十'
                seq = seq_chars[heading_index] if heading_index < len(seq_chars) else str(heading_index + 1)
                stripped = f'## {seq}、{title_content}'
                heading_index += 1
            result.append(stripped)

        # 处理 #### 及以上标题（降级为普通文本）
        elif stripped.startswith('#### '):
            stripped = re.sub(r'^#{4,}\s*', '', stripped)
            result.append(stripped)

        else:
            result.append(line)

    return '\n'.join(result)


# ============================================================
# 关键词归一化工具函数
# ============================================================

# 可构成"关键词"的字符集合
_KW_CHARS = '\\u4e00-\\u9fa5a-zA-Z0-9'
_KW_PUNCT = '（）()【】\\[\\]、·-'
_KW_COLON = '[：:]'

# 不应被识别为关键词开头的模式
_EXCLUDE_START_PATTERNS = [
    re.compile(r'^\d{1,2}:\d{2}'),   # 时间 12:30
    re.compile(r'^https?'),           # URL
    re.compile(r'^ftp'),              # URL
    re.compile(r'^file'),             # URL
    re.compile(r'^mailto'),           # URL
]


def _looks_like_keyword(text: str) -> bool:
    """判断一段文本是否像关键词"""
    if len(text) < 2 or len(text) > 30:
        return False
    if re.match(r'^\d+$', text):
        return False
    if not re.search(r'[\u4e00-\u9fa5a-zA-Z]', text):
        return False
    return True


def _find_keyword_matches(line: str) -> list:
    """查找一行中所有 "关键词：" 的位置（允许关键词与冒号间有可选空格）"""
    pattern = re.compile(rf'([{_KW_CHARS}{_KW_PUNCT}]+?)\s*{_KW_COLON}')
    matches = []
    for match in pattern.finditer(line):
        keyword = match.group(1)
        if _looks_like_keyword(keyword):
            matches.append({
                'start': match.start(),
                'end': match.end(),
                'keyword': keyword,
            })
    return matches


def _is_inside_bold(text: str, pos: int) -> bool:
    """判断某个位置是否已经在 **...** 内部"""
    before = text[:pos]
    after = text[pos:]
    bold_open = len(re.findall(r'\*\*', before))
    bold_close = len(re.findall(r'\*\*', after))
    return bold_open % 2 == 1 and bold_close >= 1


def _split_keyword_line(line: str) -> list:
    """把一行内多个关键词拆成多行"""
    matches = _find_keyword_matches(line)
    if len(matches) <= 1:
        return [line]

    parts = []
    for i in range(len(matches)):
        start = matches[i]['start']
        end = matches[i + 1]['start'] if i < len(matches) - 1 else len(line)
        part = line[start:end].strip()
        if part:
            parts.append(part)

    # 保留关键词之前的短引导语
    first_start = matches[0]['start']
    if first_start > 0:
        prefix = line[:first_start].strip()
        if prefix and len(prefix) <= 30:
            return [prefix, *parts]

    return parts


def _normalize_keyword_line(line: str) -> str:
    """把一行中的裸关键词转换为 **关键词：** 格式"""
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        return line
    # 归一化连续 * 为 **（处理LLM输出的 **** 等非标准加粗格式）
    stripped = re.sub(r'\*{2,}', '**', stripped)
    if re.match(r'^\*\*.+\*\*$', stripped):
        return stripped
    if any(p.match(stripped) for p in _EXCLUDE_START_PATTERNS):
        return line

    matches = _find_keyword_matches(stripped)
    if not matches:
        return line

    # 从后往前替换，避免索引偏移
    # 注意：每次替换后 result 长度会变化，因此后续替换必须在当前 result 上使用新的索引
    result = stripped
    for i in range(len(matches) - 1, -1, -1):
        # 在最新 result 上重新查找所有关键词位置
        current_matches = _find_keyword_matches(result)
        if i >= len(current_matches):
            continue

        match = current_matches[i]
        start = match['start']
        end = match['end']
        keyword = match['keyword']
        after_colon = result[end:].strip()

        if not after_colon:
            continue
        if _is_inside_bold(result, start):
            continue

        # 冒号放在加粗外部（**关键词**：描述），与前端 reportFormat.ts 目标格式统一
        # 避免前端再做"冒号移位"转换，减少 ** 配对错乱导致的关键词丢失
        replacement = f'**{keyword}**：{after_colon}'
        result = result[:start] + replacement

    return result


def _flatten_nested_keywords(line: str) -> str:
    """
    修正两层关键词嵌套：关键词A：关键词B：描述 → 关键词B：描述

    当一行中出现连续两个冒号关键词（关键词A：关键词B：描述），
    说明关键词A是多余的分组标题（常为命理术语，难懂），去掉只保留关键词B。

    判断条件：两个关键词之间无实质描述内容（只有空格或无内容）。
    只处理未加粗的裸关键词行，不影响已加粗的首次报告格式（**关键词：描述**（整行加粗，正文另起一行））。
    递归处理3层及以上嵌套。
    """
    # 已有 ** 加粗标记则跳过（保护首次报告的 **关键词：描述**（整行加粗，正文另起一行） 格式）
    if '**' in line:
        return line
    matches = _find_keyword_matches(line)
    if len(matches) < 2:
        return line
    # 检查是否有连续两个关键词之间无实质描述（两层嵌套）
    for i in range(len(matches) - 1):
        first = matches[i]
        second = matches[i + 1]
        between = line[first['end']:second['start']].strip()
        if not between:
            # 去掉前面的关键词，只保留第二个关键词开始的内容
            prefix = line[:first['start']].strip()
            flattened = line[second['start']:]
            result = f'{prefix} {flattened}'.strip() if prefix else flattened
            # 递归处理剩余嵌套（如三层：A：B：C：描述 → B：C：描述 → C：描述）
            return _flatten_nested_keywords(result) if result != line else result
    return line


def _normalize_keywords(content: str) -> str:
    """
    规范化关键词加粗格式。

    直接对每行做关键词加粗，不拆行。
    之前的拆分逻辑（_split_keyword_line）会把正常段落中
    出现多个"XX："的行错误拆碎，现已移除。
    """
    lines = content.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()

        # 保留空行和标题行
        if not stripped or stripped.startswith('#'):
            result.append(line)
            continue

        # 先修正两层关键词嵌套（去掉多余的分组标题关键词，如"食神格的天赋投射：兴趣启蒙方向：描述"→"兴趣启蒙方向：描述"）
        stripped = _flatten_nested_keywords(stripped)
        # 再加粗关键词
        result.append(_normalize_keyword_line(stripped))

    return '\n'.join(result)


def _normalize_lists(content: str) -> str:
    """规范化列表格式"""
    lines = content.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()

        # 处理"关键词：- 列表内容"格式（列表前有关键词）
        list_with_kw = re.match(r'^\*\*([^*：:]+[：:])\*\*\s*-\s*(.+)$', stripped)
        if list_with_kw:
            keyword = list_with_kw.group(1).rstrip('：:')
            content_text = list_with_kw.group(2)
            # 转换为段落格式（冒号在加粗外，统一格式）
            result.append(f'**{keyword}**：{content_text}')
            continue

        # 处理"- **关键词：** 描述内容"格式
        list_item_kw = re.match(r'^-\s+\*\*([^*：:]+[：:])\*\*\s*(.*)$', stripped)
        if list_item_kw:
            keyword = list_item_kw.group(1).rstrip('：:')
            description = list_item_kw.group(2).strip()
            # 转换为列表项格式（冒号在加粗外，统一格式）
            result.append(f'- **{keyword}**：{description}')
            continue

        # 处理"- 关键词：描述"格式（裸格式）
        list_item_naked = re.match(r'^-\s+([\u4e00-\u9fa5a-zA-Z0-9（）()，。！？、\s]{2,30}[：:])\s*(.+)$', stripped)
        if list_item_naked:
            keyword = list_item_naked.group(1).rstrip().rstrip('：:')
            description = list_item_naked.group(2).strip()
            result.append(f'- **{keyword}**：{description}')
            continue

        # 处理普通列表项
        if stripped.startswith('- ') or stripped.startswith('* '):
            # 确保列表项有空格
            stripped = re.sub(r'^[-*]\s*', '- ', stripped)

        result.append(stripped)

    return '\n'.join(result)


def _normalize_summary(content: str) -> str:
    """规范化总结部分"""
    lines = content.split('\n')
    result = []
    in_summary = False
    summary_start = False

    for line in lines:
        stripped = line.strip()

        # 检测总结部分开始
        if re.match(r'^##\s*💡\s*', stripped):
            in_summary = True
            # 确保标题格式正确
            stripped = re.sub(r'^##\s*💡\s*', '## 💡 ', stripped)
            result.append(line)
            continue

        # 如果在总结部分，处理关键词加粗
        if in_summary and stripped and not stripped.startswith('#'):
            # 检查是否是"关键词：内容"格式
            kw_pattern = r'^([\u4e00-\u9fa5a-zA-Z0-9（）()，。！？、\s]{2,30}[：:])(\s*.+)$'
            kw_match = re.match(kw_pattern, stripped)
            if kw_match and '**' not in stripped[:kw_match.end()]:
                keyword = kw_match.group(1).rstrip().rstrip('：:')
                rest = stripped[kw_match.end():]
                # 冒号在加粗外，统一格式
                stripped = f'**{keyword}**：{rest.strip()}'

        result.append(stripped)

    return '\n'.join(result)


def _cleanup_residuals(content: str) -> str:
    """清理残留的无效标记（健壮版：逐行处理不成对加粗）"""
    # 1. 移除空加粗（4个或更多连续*，如****）
    content = re.sub(r'\*{4,}', '', content)

    # 2. 逐行修复不成对的**（每行**数量为奇数时，移除最后一个孤立的**）
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        count = line.count('**')
        if count % 2 == 1:
            idx = line.rfind('**')
            line = line[:idx] + line[idx + 2:]
        fixed_lines.append(line)
    content = '\n'.join(fixed_lines)

    # 3. 移除无效的####
    content = re.sub(r'^####\s*', '', content, flags=re.MULTILINE)

    # 4. 移除孤立的 # 行（只有 # 没有内容的行，LLM 误用的分隔符）
    #    前端 CSS 给 h2 加了底部边框，空 <h2> 会被渲染为横线
    content = re.sub(r'^#+\s*$', '', content, flags=re.MULTILINE)

    # 5. 确保 ** 开头行之前有空行（防止段落合并）
    #    LLM 在总结部分常输出 **战术一：...**。**战术二：...**。之间没有空行，
    #    react-markdown 会把它们渲染为同一段
    lines = content.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('**') and result:
            prev_stripped = result[-1].strip()
            if prev_stripped and not prev_stripped.startswith('#'):
                result.append('')
        result.append(line)
    content = '\n'.join(result)

    # 6. 移除多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip() + '\n'


# ============================================================
# 格式检测与自动修正（步骤7.5）
# ============================================================

def _ensure_keyword_coverage(content: str) -> str:
    """
    格式检测与自动修正（输出前最后兜底）。

    规则1：每个子问题（## 标题，非总结）下至少有一个段落开头是加黑的。
           如果没有，把块内第一个段落的 "XX：YY" 裸模式加粗；
           若无冒号模式，把开头短句加粗为关键词。
    规则2：段落开头出现残破的 **（加粗失败）则先修正，再检测规则1。
    """
    lines = content.split('\n')

    # ---- 规则2：逐行修正段落开头残破的 ** ----
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('-'):
            continue
        if stripped.startswith('**'):
            lines[i] = _fix_broken_bold_opening(stripped)

    # ---- 规则1：每个子问题块至少一个段落开头加黑 ----
    block_ranges = _find_subtopic_blocks(lines)
    fixed_count = 0
    for start, end in block_ranges:
        block_indices = list(range(start + 1, end + 1))  # 排除标题行
        if _block_has_bold_opening(lines, block_indices):
            continue
        if _fix_block_no_bold(lines, block_indices):
            fixed_count += 1

    if fixed_count > 0:
        logger.info(f"[FormatNormalizer] 检测到 {fixed_count} 个子问题缺少加粗关键词，已自动修正")

    return '\n'.join(lines)


def _find_subtopic_blocks(lines: list) -> list:
    """识别子问题块边界（## 标题且非 ## 💡 总结），返回 [(start_idx, end_idx), ...]"""
    blocks = []
    current_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('## ') and not stripped.startswith('## 💡'):
            if current_start is not None:
                blocks.append((current_start, i - 1))
            current_start = i
        elif stripped.startswith('## 💡'):
            if current_start is not None:
                blocks.append((current_start, i - 1))
                current_start = None
    if current_start is not None:
        blocks.append((current_start, len(lines) - 1))
    return blocks


def _fix_broken_bold_opening(line: str) -> str:
    """
    修正段落开头残破的 ** 加粗（加粗失败导致字面 ** 显示）。

    修正场景：
    - ** 后紧跟空格（** 关键词**）→ 去空格
    - 闭合 ** 前有空格（**关键词 **）→ 去空格（仅处理首个 ** 对，不影响行内其他加粗）
    - 奇数 **（未配对）→ 移除开头残破 **（兜底，正常情况 _cleanup_residuals 已处理）
    - **关键词** 后跟非冒号字符（**关键词**描述）→ 补冒号
    - 首次报告的 **关键词：描述**（整行加粗，正文另起一行） 不受影响（关键词含冒号，跳过补冒号）
    """
    # 1. ** 后紧跟空格 → 去空格
    fixed = re.sub(r'^\*\*\s+', '**', line)
    # 2. 闭合 ** 前有空格 → 去空格（仅首个 ** 对）
    fixed = re.sub(r'^(\*\*[^*]+?)\s+\*\*', r'\1**', fixed)
    # 3. 奇数 ** → 移除开头残破的 **
    if fixed.count('**') % 2 == 1:
        fixed = re.sub(r'^\*\*', '', fixed, count=1)
    # 4. **关键词** 后跟非冒号非空格字符 → 补冒号（关键词内含冒号则跳过，兼容首次报告格式）
    bold_match = re.match(r'^\*\*([^*]+)\*\*\s*([^：:\s].*)$', fixed)
    if bold_match:
        keyword = bold_match.group(1)
        rest = bold_match.group(2)
        if not re.search(r'[：:]', keyword):
            fixed = f'**{keyword}**：{rest}'
    return fixed


def _block_has_bold_opening(lines: list, indices: list) -> bool:
    """检查块内是否有至少一行包含加粗关键词（支持追问报告 **关键词**：描述 和首次报告 **关键词：描述** 两种格式）"""
    for idx in indices:
        line = lines[idx].strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        # 追问报告格式：**关键词**：描述（加粗后跟冒号在加粗外）
        if re.search(r'\*\*[^*]+\*\*\s*[：:]', line):
            return True
        # 首次报告格式：**关键词：描述**（整行加粗，冒号在加粗内）
        if re.match(r'^\*\*[^*]+：[^*]*\*\*$', line):
            return True
    return False


def _fix_block_no_bold(lines: list, indices: list) -> bool:
    """
    对没有加粗关键词的子问题块进行修正。

    修正策略（按优先级）：
    1. 块内第一个非空段落若有 "XX：YY" 裸模式 → 加粗为 **XX**：YY
    1b. 若有 "**XX** YY" 模式（已加粗但无冒号）→ 补冒号为 **XX**：YY
    2. 无冒号模式 → 把开头短句（到第一个逗号或句号）加粗为关键词

    Returns: True 表示成功修正
    """
    for idx in indices:
        line = lines[idx].strip()
        if not line or line.startswith('#') or line.startswith('-'):
            continue
        # 策略1：匹配 "XX：YY" 裸模式（无加粗的冒号关键词）
        kw_match = re.match(r'^([\u4e00-\u9fa5a-zA-Z0-9（）()、·\-]{2,15})[：:]\s*(.+)$', line)
        if kw_match:
            keyword = kw_match.group(1)
            desc = kw_match.group(2)
            lines[idx] = f'**{keyword}**：{desc}'
            return True
        # 策略1b：匹配 "**XX** YY" 模式（已加粗但无冒号，补冒号）
        # 排除加粗内容中已含冒号的情况（首次报告的 **关键词：描述**（整行加粗，正文另起一行） 格式）
        bold_no_colon = re.match(r'^\*\*([^*：:]+)\*\*\s+(.+)$', line)
        if bold_no_colon:
            keyword = bold_no_colon.group(1)
            desc = bold_no_colon.group(2)
            lines[idx] = f'**{keyword}**：{desc}'
            return True
        # 策略2a：无冒号模式，把开头短句（到第一个逗号）加粗为关键词
        punct_match = re.match(r'^([\u4e00-\u9fa5a-zA-Z0-9]{2,20})([，,])(.*)$', line)
        if punct_match:
            keyword = punct_match.group(1)
            punct = punct_match.group(2)
            rest = punct_match.group(3)
            lines[idx] = f'**{keyword}**{punct}{rest}' if rest else f'**{keyword}**'
            return True
        # 策略2b：无逗号有句号，把开头短句（2-8字，到句号）加粗为关键词
        period_match = re.match(r'^([\u4e00-\u9fa5a-zA-Z0-9]{2,8})([。.！!])(.*)$', line)
        if period_match:
            keyword = period_match.group(1)
            punct = period_match.group(2)
            rest = period_match.group(3)
            lines[idx] = f'**{keyword}**{punct}{rest}' if rest else f'**{keyword}**'
            return True
        # 兜底：无法识别关键词结构，跳过（不强行加粗避免破坏内容）
        return False
    return False


# ============================================================
# 辅助函数
# ============================================================

def validate_format(content: str) -> List[str]:
    """
    验证格式合规性，返回问题列表。

    Returns:
        问题列表，每项为 (问题描述, 位置)
    """
    issues = []
    lines = content.split('\n')

    # 检查1：是否有子问题拆解（至少两个一级标题）
    h2_count = len([l for l in lines if l.strip().startswith('## ') and not l.strip().startswith('## 💡')])
    if h2_count < 2:
        issues.append("缺少子问题拆解（至少需要2个一级标题）")

    # 检查2：是否有总结部分
    has_summary = any('💡' in l for l in lines if l.strip().startswith('## '))
    if not has_summary:
        issues.append("缺少总结部分（需要## 💡 标题）")

    # 检查3：检查关键词加粗情况
    keyword_lines = [l.strip() for l in lines if re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9（）()，。！？、\s]{2,30}[：:]', l.strip())]
    unbolded_kw = [l for l in keyword_lines if '**' not in l]
    if unbolded_kw:
        issues.append(f"有 {len(unbolded_kw)} 处关键词未加粗")

    return issues


def is_format_valid(content: str, min_score: float = 0.7) -> bool:
    """
    快速判断格式是否有效。

    Args:
        content: 待检查内容
        min_score: 最低合规分数（0-1）

    Returns:
        是否合规
    """
    issues = validate_format(content)
    total_checks = 4  # 总检查项数
    passed_checks = total_checks - len(issues)
    score = passed_checks / total_checks

    return score >= min_score