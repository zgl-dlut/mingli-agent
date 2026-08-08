"""
结构化追问报告服务

LLM 输出 JSON（response_format=json_object），后端容错+校验，
直接存 JSON 到数据库，前端用 React 组件直渲染（不走 Markdown 中间层）。

与首次报告解读链路完全隔离，互不影响。
"""
import json
import time
import logging
from typing import AsyncGenerator, Dict, List

from pydantic import ValidationError

from app.schemas.report_schema import FollowupReport
from app.services.skill_prompts import _build_context_vars
from app.services.ai_service import model_pool, get_client

logger = logging.getLogger(__name__)


# ============================================================
# 精简 prompt（只含命理逻辑 + JSON 结构示例，不含任何格式规则）
# ============================================================

def build_structured_prompt(context: dict) -> str:
    """构建结构化追问 prompt：命理逻辑 + JSON 结构示例"""
    return f"""# 角色
专业命理咨询从业者，主打专业命理内核 + 大白话落地解读。摒弃晦涩玄学话术，专为零基础小白服务，先给结论、给决策、给具体做法，保留精准流年流月推演。

# 命盘数据
咨询时间：{context['current_time']}，{context['liunian_ganzhi']}流年{context['liunian_season']}
日主：{context['rizhu']}（{context['gender']}）
四柱：{context['sizu']}
旺衰：{context['wangshuai']}
格局：{context['geju_description']}
用神：{context['yongshen']}，忌神：{context['jishen']}
十神特征：{context['shishen_fenbu']}
五行分布：{context['wuxing_fenbu']}
地支作用：{context['dizhi_zuoyong']}
调候：{context['tiaohou_desc']}
当前大运：{context['current_dayun']}
大运解读：{context['dayun_jiedu']}
重点流年：{context['key_liunian']}
年龄：{context['age']}岁，{context['age_stage']}

# 用户问题
{context['user_question']}

# 输出格式
请输出纯JSON（不要用```json代码块包裹，直接输出JSON文本），结构如下：

{{
  "opening": {{
    "lead": "开篇叙事(可选)。1-2句，形式多样，可内联**加粗**重要词。不要每次都用'直接回答你'开头",
    "verdict": "核心结论(可选)。一句话定调，可内联**加粗**"
  }},
  "subtopics": [
    {{
      "title": "子问题标题，直接引用或微调用户原话",
      "blocks": [
        {{"type": "keyword", "keyword": "叙事化关键词，不加**号", "narrative": "描述2-3句，可内联**加粗**，术语用括号解释", "term_explain": "可选，术语单独解释", "sub_items": ["可选子要点1", "子要点2"]}},
        {{"type": "narrative", "text": "纯叙事段落，无关键词"}},
        {{"type": "group", "title": "小标题", "paragraphs": ["段落1", "段落2"]}}
      ]
    }}
  ],
  "summary": {{
    "title": "总结动态副标题",
    "style_hint": "可选，风格描述",
    "lead": "可选引导语，在items前输出，可内联**加粗**",
    "items": [{{"keyword": "阶段名", "text": "描述"}}],
    "item_format": "可选，items渲染格式：list(列表式,默认)或paragraph(段落式,无前缀)",
    "narrative": "可选整段叙事(与items二选一)",
    "closing": "可选收尾一句话"
  }}
}}

注意：
- opening的lead和verdict都可选，至少填一个
- blocks里每个subtopic放1-3个block，type可选keyword/narrative/group
- summary的items和narrative二选一
- keyword字段不要加**号（前端组件自动加粗）
- 所有字符串值必须是单行，不能直接换行。如需分段用\\n\\n转义

# 命理分析要求（只管内容，不管格式）

1. **拆解数量=用户问题数量**：用户问了几个独立问题就拆几个subtopic，禁止为凑篇幅强行拆分
2. **结论前置**：opening.lead 或 verdict 直接给出核心答案，让用户3秒抓核心
3. **开篇不固化开头（重要）**：lead 字段形式多样，每次从以下风格中随机选一种，**严禁每次都用"直接回答你"开头**：
   - 结论直击式：直接抛出核心答案，如"这两年不仅不该回避，反而是你近十年最该出手的窗口。"
   - 情绪反转式：先说大众认知再反转，如"很多人觉得动荡期不能碰大资产，但你的命盘恰恰相反。"
   - 痛点直击式：点出用户焦虑，如"你怕的'压力'，本质是现金流被锁死，而不是不能买。"
   - 不加粉饰直击式：朴素陈述，如"先给结论：26、27年不买是明智的，但你真正该等的是2033年。"
   1-2句，禁止用"站在X月节点""距离立秋"等时间节点式开头
4. **命理术语必须解释**：narrative/term_explain里出现术语（财星破印、七杀、伤官等）必须紧跟通俗解释，用括号或"="或"也就是"连接
5. **子问题标题贴合用户原话**：title直接引用或微调用户原话，不要替换成命理术语
6. **关键词叙事化**：keyword字段从段落内容抽象出有故事性、结论感的短语，贴合子问题
7. **流月数据基于排盘**：涉及具体月份建议时，基于重点流年数据，不自行推测
8. **内联加粗**：narrative/text字段里重要文字（时间、金额、结论）可用**加粗**，但不要整段加粗
9. **篇幅精简**：每个keyword的narrative控制在2-3句，不堆砌冗余分析
10. **总结风格多样**：summary的style_hint每次选不同风格（三阶段节奏/行动清单/时间轴等），items的keyword叙事化
"""


# ============================================================
# JSON 容错提取（处理 LLM 输出的格式偏差）
# ============================================================

def _extract_and_fix_json(raw: str) -> str:
    """容错提取 JSON：截取第一个完整JSON对象 + 去掉markdown包裹 + 修复字符串值裸换行"""
    text = raw.strip()

    # 第一层：去掉 ```json ... ``` 包裹
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # 第二层：截取第一个完整的 JSON 对象（处理超长重复输出）
    start_idx = text.find("{")
    if start_idx < 0:
        return text

    depth = 0
    in_string = False
    escape_next = False
    end_idx = -1
    for i, ch in enumerate(text[start_idx:], start_idx):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    if end_idx > start_idx:
        text = text[start_idx:end_idx]
    else:
        text = text[start_idx:]

    # 第三层：修复 JSON 字符串值里的裸换行
    result = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue
        if ch == "\n" and in_string:
            result.append("\\n")
            continue
        result.append(ch)

    return "".join(result)


# ============================================================
# 结构化追问生成（主入口）
# ============================================================

async def generate_followup_structured(
    analysis_data: Dict,
    gender: str,
    birth_date: str,
    birth_time: str,
    location: str,
    user_question: str,
    history: List[dict],
) -> AsyncGenerator[str, None]:
    """
    结构化追问报告生成：
    1. 构建命盘上下文 + 精简 prompt
    2. 调用 LLM（response_format=json_object，非流式）
    3. 容错提取 + Pydantic 校验
    4. yield JSON 字符串（一次性，非流式）

    返回的 JSON 字符串可直接存库，前端解析后用 React 组件渲染。
    """
    # 1. 构建命盘上下文
    context = _build_context_vars(
        analysis_data=analysis_data,
        gender=gender,
        user_question=user_question,
        birth_date=birth_date,
    )

    # 2. 构建精简 prompt（不含格式规则）
    system_prompt = build_structured_prompt(context)

    # 3. 构建 messages（history + user_question）
    messages = history + [{"role": "user", "content": user_question}]

    # 4. 调用 LLM（复用 ai_service 的 model_pool，取第一个可用模型）
    if not model_pool:
        yield json.dumps({"opening": {"lead": "AI模型未配置"}, "subtopics": [], "summary": {"title": "错误"}}, ensure_ascii=False)
        return
    model_config = model_pool[0]
    client = await get_client(model_config)

    logger.info(f"[StructuredFollowup] 开始生成, 模型={model_config.name}, 问题: {user_question[:50]}..., prompt长度: {len(system_prompt)}")

    start = time.time()
    response = await client.chat.completions.create(
        model=model_config.name,
        messages=[{"role": "system", "content": system_prompt}] + messages,
        temperature=0.3,
        max_tokens=6000,
        response_format={"type": "json_object"},
        timeout=120,
    )

    raw_content = response.choices[0].message.content or ""
    finish_reason = response.choices[0].finish_reason
    elapsed = time.time() - start
    logger.info(f"[StructuredFollowup] LLM响应: finish_reason={finish_reason}, 长度={len(raw_content)}, 耗时={elapsed:.1f}s")

    # 5. 解析 + 容错 + 校验
    try:
        data = json.loads(raw_content)
        logger.info("[StructuredFollowup] JSON直接解析成功")
    except json.JSONDecodeError:
        logger.info("[StructuredFollowup] JSON直接解析失败，启动容错修复...")
        fixed = _extract_and_fix_json(raw_content)
        try:
            data = json.loads(fixed)
            logger.info("[StructuredFollowup] 容错修复后解析成功")
        except json.JSONDecodeError as e:
            logger.error(f"[StructuredFollowup] JSON解析彻底失败: {e}")
            # 降级：返回错误JSON，前端显示兜底提示
            error_report = {
                "opening": {"lead": "报告生成异常，请稍后重试。"},
                "subtopics": [],
                "summary": {"title": "生成失败"},
            }
            yield json.dumps(error_report, ensure_ascii=False)
            return

    # 6. Pydantic 校验
    try:
        report = FollowupReport.model_validate(data)
        logger.info(f"[StructuredFollowup] Pydantic校验通过, subtopics={len(report.subtopics)}")
    except ValidationError as e:
        logger.error(f"[StructuredFollowup] Pydantic校验失败: {e}")
        error_report = {
            "opening": {"lead": "报告格式异常，请稍后重试。"},
            "subtopics": [],
            "summary": {"title": "校验失败"},
        }
        yield json.dumps(error_report, ensure_ascii=False)
        return

    # 7. yield JSON 字符串（存库用）
    yield json.dumps(data, ensure_ascii=False)
