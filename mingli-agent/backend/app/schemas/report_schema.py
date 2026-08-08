"""
追问报告结构化 Schema（POC）

用 Pydantic 模型定义报告的 JSON 结构，LLM 按此结构输出 JSON，
后端用模板渲染成标准 Markdown。

设计原则：
- 宏观结构（段落、标题、关键词位置）= schema 强制
- 微观加粗（句中哪些词加粗）= 文本字段内联 ** 标记，原样保留给 react-markdown
- 开篇不固化开头用词，只定义 lead + verdict 两个可选字段
"""
from typing import List, Optional, Literal, Union, Annotated

from pydantic import BaseModel, Field


# ============================================================
# 开篇
# ============================================================

class Opening(BaseModel):
    """开篇承接 + 整体定调。两个字段都可选，至少填一个。"""
    lead: Optional[str] = Field(
        None,
        description="承接叙事，1-2句，形式多样（结论直击/情绪反转/痛点直击/不加粉饰直击）。"
                    "不约束开头用词，可内联**加粗**重要词。可用\\n\\n分段。不含关键词标记。"
    )
    verdict: Optional[str] = Field(
        None,
        description="整体定调/核心结论一句话，可内联**加粗**关键词。"
    )


# ============================================================
# 子问题内部 block（三种类型，discriminated union）
# ============================================================

class KeywordBlock(BaseModel):
    """关键词段落：**关键词**：描述内容"""
    type: Literal["keyword"] = "keyword"
    keyword: str = Field(description="叙事化关键词短语，贴合子问题，可含命理术语+括号解释")
    narrative: str = Field(description="描述内容2-3句，可内联**加粗**，命理术语用(括号)或=解释")
    term_explain: Optional[str] = Field(None, description="可选，命理术语单独解释一句")
    sub_items: Optional[List[str]] = Field(
        None, description="可选，并列子要点列表，每项独占一行渲染为 - 列表项"
    )


class NarrativeBlock(BaseModel):
    """纯叙事段落：无关键词，用于过渡或补充分析"""
    type: Literal["narrative"] = "narrative"
    text: str = Field(description="纯叙事段落文本，可内联**加粗**")


class GroupBlock(BaseModel):
    """分组展开块：小标题 + 多段正文（适合复杂命理分析）"""
    type: Literal["group"] = "group"
    title: str = Field(description="小标题，叙事化，可含命理术语+括号解释")
    paragraphs: List[str] = Field(description="正文段落列表，每段可内联**加粗**")


# discriminated union：用 type 字段区分
Block = Annotated[
    Union[KeywordBlock, NarrativeBlock, GroupBlock],
    Field(discriminator="type"),
]


# ============================================================
# 子问题
# ============================================================

class Subtopic(BaseModel):
    """一个子问题：标题 + blocks"""
    title: str = Field(
        description="子问题标题，直接引用或微调用户原话，贴合用户问题核心关切。"
                    "不要用命理术语，让用户一眼看出在回答他的哪个问题"
    )
    blocks: List[Block] = Field(
        description="子问题内部段落，1-3个block。简单结论用keyword，"
                    "过渡补充用narrative，复杂命理分析用group"
    )


# ============================================================
# 总结
# ============================================================

class SummaryItem(BaseModel):
    """总结里的并列项"""
    keyword: str = Field(description="阶段/要点关键词")
    text: str = Field(description="对应描述，可内联**加粗**")


class Summary(BaseModel):
    """总结部分。支持两种形式：items列表 或 narrative整段叙事"""
    title: str = Field(description='总结标题，格式：💡 总结：动态副标题')
    style_hint: Optional[str] = Field(
        None, description="可选，总结风格描述（如三阶段节奏/行动清单/时间轴），LLM自选不强制枚举"
    )
    lead: Optional[str] = Field(
        None, description="引导语，在items前输出。可内联**加粗**（加粗或不加粗均可）"
    )
    items: Optional[List[SummaryItem]] = Field(
        None, description="并列项列表（三阶段/清单/时间轴等）。与 narrative 二选一"
    )
    item_format: Optional[Literal["list", "paragraph"]] = Field(
        "list", description="items渲染格式：list=列表式(- **关键词**：描述)，"
                            "paragraph=段落式(**关键词**：描述无前缀)。默认list"
    )
    narrative: Optional[str] = Field(
        None, description="整段叙事式总结（无并列项时用）。与 items 二选一"
    )
    closing: Optional[str] = Field(None, description="可选收尾一句话")


# ============================================================
# 完整报告
# ============================================================

class FollowupReport(BaseModel):
    """追问报告完整结构"""
    opening: Opening = Field(description="开篇")
    subtopics: List[Subtopic] = Field(
        description="子问题列表。数量=用户问的独立问题数量，禁止为凑篇幅强行拆分"
    )
    summary: Summary = Field(description="总结")


# ============================================================
# 导出 JSON schema（给 LLM 用）
# ============================================================

def get_report_json_schema() -> dict:
    """导出 JSON schema dict，用于 LLM 的 response_format 或 prompt 注入"""
    return FollowupReport.model_json_schema()


if __name__ == "__main__":
    import json
    schema = get_report_json_schema()
    print(json.dumps(schema, ensure_ascii=False, indent=2))
