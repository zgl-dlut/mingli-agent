"""
报告渲染器：将 FollowupReport JSON 渲染成标准 Markdown。

格式规则集中在本文件，改格式只改这里，不碰 prompt、不碰正则、不碰前端。
内联 **加粗**（LLM 在文本字段里加的）原样保留，react-markdown 原生渲染。
"""
from typing import Dict, Any
import json

from app.schemas.report_schema import (
    FollowupReport, Opening, Subtopic,
    KeywordBlock, NarrativeBlock, GroupBlock,
    Summary, SummaryItem,
)


def render_report(report: Dict[str, Any]) -> str:
    """
    将 LLM 输出的 JSON dict 渲染成标准 Markdown。

    Args:
        report: FollowupReport 结构的 dict（来自 LLM JSON 输出）

    Returns:
        标准 Markdown 字符串
    """
    # 先用 Pydantic 校验结构（不合法会抛异常，调用方处理）
    model = FollowupReport.model_validate(report)
    return _render(model)


def render_report_from_json(json_str: str) -> str:
    """从 JSON 字符串渲染"""
    data = json.loads(json_str)
    return render_report(data)


def _render(report: FollowupReport) -> str:
    sections: list[str] = []

    # 1. 开篇
    opening_md = _render_opening(report.opening)
    if opening_md:
        sections.append(opening_md)

    # 2. 子问题
    for i, subtopic in enumerate(report.subtopics):
        sections.append(_render_subtopic(subtopic, i + 1))

    # 3. 总结
    sections.append(_render_summary(report.summary))

    return "\n\n".join(sections)


def _render_opening(opening: Opening) -> str:
    """渲染开篇：lead（可\n\n分段）+ verdict，非空才渲染"""
    parts: list[str] = []
    if opening.lead:
        # lead 里的 \n\n 作为段落分隔
        lead_paragraphs = opening.lead.split("\\n\\n")
        # 也处理真实换行的 \n\n
        if len(lead_paragraphs) == 1:
            lead_paragraphs = opening.lead.split("\n\n")
        parts.append("\n\n".join(p.strip() for p in lead_paragraphs if p.strip()))
    if opening.verdict:
        parts.append(opening.verdict.strip())
    return "\n\n".join(parts)


def _render_subtopic(subtopic: Subtopic, index: int) -> str:
    """渲染子问题：标题 + blocks"""
    lines: list[str] = []

    # 中文数字序号
    seq_chars = "一二三四五六七八九十"
    seq = seq_chars[index - 1] if index <= len(seq_chars) else str(index)
    lines.append(f"## {seq}、{subtopic.title}")

    for block in subtopic.blocks:
        lines.append("")  # 标题/blocks 间空行
        if isinstance(block, KeywordBlock):
            lines.append(_render_keyword_block(block))
        elif isinstance(block, NarrativeBlock):
            lines.append(block.text.strip())
        elif isinstance(block, GroupBlock):
            lines.append(_render_group_block(block))

    return "\n".join(lines)


def _render_keyword_block(block: KeywordBlock) -> str:
    """渲染关键词段落：**keyword**：narrative + 可选sub_items"""
    parts: list[str] = []

    # 关键词行：**关键词**：描述（冒号在加粗外）
    main_line = f"**{block.keyword}**：{block.narrative.strip()}"
    parts.append(main_line)

    # 子要点列表（如有）
    if block.sub_items:
        parts.append("")
        for item in block.sub_items:
            parts.append(f"- {item.strip()}")

    return "\n".join(parts)


def _render_group_block(block: GroupBlock) -> str:
    """渲染分组块：**小标题** + 多段正文"""
    parts: list[str] = []
    parts.append(f"**{block.title}**")
    for para in block.paragraphs:
        parts.append("")
        parts.append(para.strip())
    return "\n".join(parts)


def _render_summary(summary: Summary) -> str:
    """渲染总结"""
    lines: list[str] = []
    lines.append(f"## 💡 {summary.title}")

    # 引导语（在items/narrative前输出）
    if summary.lead:
        lines.append("")
        lines.append(summary.lead.strip())

    if summary.items:
        lines.append("")
        fmt = summary.item_format or "list"
        for item in summary.items:
            if fmt == "paragraph":
                # 段落式：**关键词**：描述（无前缀，每项独占一段）
                lines.append(f"**{item.keyword}**：{item.text.strip()}")
                lines.append("")
            else:
                # 列表式：- **关键词**：描述
                lines.append(f"- **{item.keyword}**：{item.text.strip()}")
    elif summary.narrative:
        lines.append("")
        # narrative 里的 \n\n 分段
        paragraphs = summary.narrative.split("\n\n")
        lines.append("\n\n".join(p.strip() for p in paragraphs if p.strip()))

    if summary.closing:
        lines.append("")
        lines.append(summary.closing.strip())

    return "\n".join(lines)
