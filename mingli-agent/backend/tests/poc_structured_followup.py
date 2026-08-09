"""
POC：结构化追问报告验证脚本

验证目标：
1. qwen3.7-flash 能否稳定输出符合 schema 的 JSON
2. JSON 约束下命理叙事质量（术语解释、加粗、故事性）
3. 渲染器输出的 Markdown 是否符合预期格式

运行：cd backend && python -m tests.poc_structured_followup
"""
import asyncio
import json
import sys
import os
import time

# 确保能 import app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import AsyncOpenAI

from app.config import settings
from app.schemas.report_schema import FollowupReport, get_report_json_schema
from app.services.report_renderer import render_report
from app.services.skill_prompts import _build_context_vars
from app.skills.orchestrator import generate_full_analysis


# ============================================================
# 测试命例（壬申 壬子 己巳 甲戌）
# ============================================================
BIRTH_DATE = "1992-12-19"
BIRTH_TIME = "19:35"
LONGITUDE = 116.4
LATITUDE = 39.9
GENDER = "男"
LOCATION = "北京"

# 测试问题（用户之前问的买房问题）
TEST_QUESTION = "那是不是未来十年我尽量不买房，26、27年肯定不会买；未来我更能没有压力的购入房产的时间点是什么时候"


# ============================================================
# 精简 prompt（只含命理逻辑 + schema 说明，不含任何格式规则）
# ============================================================

def build_structured_prompt(context: dict) -> str:
    """构建结构化追问 prompt：命理逻辑 + JSON 结构示例（不用完整schema，避免LLM误输出schema本身）"""
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
        {{"type": "keyword", "keyword": "叙事化关键词，不加**号", "narrative": "描述2-3句，可内联**加粗**，术语用括号或'='融合解释，禁止单独成段", "sub_items": ["可选子要点1", "子要点2"]}},
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
- keyword字段不要加**号（后端自动加粗）
- 所有字符串值必须是单行，不能直接换行。如需分段用\\n\\n转义

# 命理分析要求（只管内容，不管格式）

1. **子问题拆解（核心规则，必须执行）**：必须把用户问题拆解为多个 subtopic，禁止整段叙事不拆分。先识别用户问题里的所有子点，每个子点至少对应一个 subtopic；再补充关键分析维度（风险/避坑、时间路线图、五行喜忌、行动策略等）作为额外 subtopic。建议拆 2-4 个，覆盖用户所有子点 + 必要的风险/策略维度，禁止只输出1个。本题可拆3个：①黄金购房节点(2028-2029) ②2032危机核心是杠杆不是房子 ③十年买房化灾路线图
2. **结论前置**：opening.lead 或 verdict 直接给出核心答案，让用户3秒抓核心
3. **开篇不固化开头（重要）**：lead 字段形式多样，每次从以下风格中随机选一种，**严禁每次都用"直接回答你"开头**：
   - 结论直击式：直接抛出核心答案，如"这两年不仅不该回避，反而是你近十年最该出手的窗口。"
   - 情绪反转式：先说大众认知再反转，如"很多人觉得动荡期不能碰大资产，但你的命盘恰恰相反。"
   - 痛点直击式：点出用户焦虑，如"你怕的'压力'，本质是现金流被锁死，而不是不能买。"
   - 不加粉饰直击式：朴素陈述，如"先给结论：26、27年不买是明智的，但你真正该等的是2033年。"
   1-2句，禁止用"站在X月节点""距离立秋"等时间节点式开头
4. **命理术语必须解释**：narrative里出现术语（财星破印、七杀、伤官等）必须紧跟通俗解释，用括号或"="或"也就是"连接，融入句子，禁止单独成段
5. **子问题标题贴合用户原话**：title直接引用或微调用户原话，不要替换成命理术语
6. **关键词叙事化**：keyword字段从段落内容抽象出有故事性、结论感的短语，贴合子问题
7. **流月数据基于排盘**：涉及具体月份建议时，基于重点流年数据，不自行推测
8. **内联加粗**：narrative/text字段里重要文字（时间、金额、结论）可用**加粗**，但不要整段加粗
9. **篇幅精简**：每个keyword的narrative控制在2-3句，不堆砌冗余分析。2个subtopic总计不超过1300字
10. **总结风格多样**：summary的style_hint每次选不同风格（三阶段节奏/行动清单/时间轴等），items的keyword叙事化
"""


# ============================================================
# LLM 调用（非流式，response_format=json_object）
# ============================================================

def _extract_and_fix_json(raw: str) -> str:
    """容错提取 JSON：截取第一个完整JSON对象 + 去掉markdown包裹 + 修复字符串值裸换行"""
    raw_len = len(raw)
    text = raw.strip()

    # ── 第一层：去掉 ```json ... ``` 包裹 ──
    markdown_stripped = False
    if text.startswith("```"):
        markdown_stripped = True
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # ── 第二层：截取第一个完整的 JSON 对象（处理超长重复输出）──
    start_idx = text.find("{")
    if start_idx < 0:
        print(f"  [容错] 原始长度={raw_len}, 未找到{{, 返回原始文本")
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

    truncated = False
    pre_truncate_len = len(text)
    if end_idx > start_idx:
        text = text[start_idx:end_idx]
        truncated = pre_truncate_len > len(text)
    else:
        # 括号未配平（JSON被截断），只截取到末尾
        text = text[start_idx:]
        truncated = True

    # ── 第三层：修复 JSON 字符串值里的裸换行：在引号内的 \n 替换为 \\n ──
    result = []
    in_string = False
    escape_next = False
    bare_newline_count = 0
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
            bare_newline_count += 1
            continue
        result.append(ch)

    fixed_text = "".join(result)

    # ── 日志汇总 ──
    print(f"  [容错] 原始长度={raw_len} → 最终长度={len(fixed_text)}")
    if markdown_stripped:
        print(f"  [容错] ✂ 去掉了 markdown 包裹")
    if truncated:
        print(f"  [容错] ✂ 截取了重复/截断部分: {pre_truncate_len} → {len(text)} 字符")
    else:
        print(f"  [容错] ✓ 无重复输出，未截取")
    if bare_newline_count > 0:
        print(f"  [容错] 🔧 修复了 {bare_newline_count} 处字符串值裸换行")
    else:
        print(f"  [容错] ✓ 无裸换行需修复")

    return fixed_text


async def call_llm_structured(system_prompt: str, user_question: str) -> str:
    """调用 LLM 输出 JSON"""
    api_key = settings.DASHSCOPE_API_KEY or settings.OPENAI_API_KEY
    base_url = settings.AI_BASE_URL

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    print(f"[POC] 调用模型: {settings.AI_MODELS}")
    print(f"[POC] 用户问题: {user_question}")
    print(f"[POC] prompt长度: {len(system_prompt)} 字符")
    print("-" * 60)

    start = time.time()

    # response_format 在此API上必需（不带则返回空），但会导致超长重复输出
    # 去掉 penalty（可能不被支持），max_tokens 适当放大
    response = await client.chat.completions.create(
        model=settings.AI_MODELS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
        temperature=0.3,
        max_tokens=6000,
        response_format={"type": "json_object"},
        timeout=120,
    )

    content = response.choices[0].message.content or ""
    finish_reason = response.choices[0].finish_reason
    print(f"[POC] finish_reason={finish_reason}, content长度={len(content)}")

    elapsed = time.time() - start
    print(f"[POC] LLM响应耗时: {elapsed:.1f}s")
    print()
    return content


# ============================================================
# 主流程
# ============================================================

async def main():
    # 1. 生成命盘数据
    print("=" * 60)
    print("[步骤1] 生成命盘数据")
    print("=" * 60)
    analysis_data = generate_full_analysis(
        birth_date=BIRTH_DATE,
        birth_time=BIRTH_TIME,
        longitude=LONGITUDE,
        latitude=LATITUDE,
        gender=GENDER,
        location=LOCATION,
    )
    print(f"命盘生成完成，日主: {analysis_data.get('日主', 'N/A')}")
    print()

    # 2. 构建命盘上下文
    context = _build_context_vars(
        analysis_data=analysis_data,
        gender=GENDER,
        user_question=TEST_QUESTION,
        birth_date=BIRTH_DATE,
    )

    # 3. 构建 prompt（用简化结构示例，不用完整schema避免LLM误输出schema本身）
    system_prompt = build_structured_prompt(context)

    # 4. 调用 LLM
    print("=" * 60)
    print("[步骤2] 调用 LLM 生成结构化 JSON")
    print("=" * 60)
    raw_json = await call_llm_structured(system_prompt, TEST_QUESTION)

    # 5. 校验 JSON
    print("=" * 60)
    print("[步骤3] Pydantic 校验 JSON 结构")
    print("=" * 60)
    try:
        data = json.loads(raw_json)
        top_keys = list(data.keys()) if isinstance(data, dict) else f"(非dict: {type(data).__name__})"
        print(f"[解析] 直接解析成功, 长度={len(raw_json)}, 顶层keys={top_keys}")
    except json.JSONDecodeError:
        # 容错：修复字符串值里的裸换行
        print("[解析] 直接解析失败，启动容错修复...")
        fixed = _extract_and_fix_json(raw_json)
        try:
            data = json.loads(fixed)
            top_keys = list(data.keys()) if isinstance(data, dict) else f"(非dict: {type(data).__name__})"
            print(f"[解析] 容错修复后解析成功, 顶层keys={top_keys}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON 解析失败（容错后仍失败）: {e}")
            print("\n原始输出（前800字符）:")
            print(raw_json[:800])
            return

    try:
        report = FollowupReport.model_validate(data)
        print("✅ JSON 结构校验通过")
    except Exception as e:
        print(f"❌ Pydantic 校验失败: {e}")
        # 诊断：对比期望keys与实际keys，快速定位"LLM输出schema本身"等问题
        if isinstance(data, dict):
            expected_keys = {"opening", "subtopics", "summary"}
            actual_keys = set(data.keys())
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            if missing:
                print(f"  ❌ 缺失字段: {missing}")
            if extra:
                print(f"  ⚠️ 多余字段: {extra}（可能误输出了schema本身或其他结构）")
            if not missing and not extra:
                print(f"  字段齐全，问题在子结构（blocks类型/嵌套等）")
        print("\nLLM 输出的 JSON（前1000字符）:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
        return

    # 6. 渲染 Markdown
    print()
    print("=" * 60)
    print("[步骤4] 渲染成 Markdown")
    print("=" * 60)
    markdown = render_report(data)
    print(markdown)

    # 7. 统计
    print()
    print("=" * 60)
    print("[步骤5] 验证统计")
    print("=" * 60)
    print(f"子问题数量: {len(report.subtopics)}")
    for i, sub in enumerate(report.subtopics):
        block_types = [b.type for b in sub.blocks]
        print(f"  subtopic[{i}] '{sub.title}': {len(sub.blocks)} blocks {block_types}")
    print(f"开篇 lead: {'有' if report.opening.lead else '无'}")
    print(f"开篇 verdict: {'有' if report.opening.verdict else '无'}")
    print(f"开篇lead开头: {(report.opening.lead or '')[:30]}...")
    print(f"总结 items: {len(report.summary.items) if report.summary.items else '无(narrative模式)'}")
    print(f"Markdown总长度: {len(markdown)} 字符")

    # 8. 检查是否有重复段落
    lines = [l.strip() for l in markdown.split("\n") if l.strip()]
    seen = set()
    duplicates = []
    for line in lines:
        if line in seen:
            duplicates.append(line[:50])
        seen.add(line)
    if duplicates:
        print(f"⚠️  发现重复行: {len(duplicates)} 处")
        for d in duplicates:
            print(f"  - {d}")
    else:
        print("✅ 无重复段落")


if __name__ == "__main__":
    asyncio.run(main())
