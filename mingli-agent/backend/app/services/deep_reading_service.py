"""AI 深度解读：大纲生成服务

两段式咨询的第一段。用户在对话中提出一个问题后，先只产出「分析框架」：
一句框架性开场 + 若干分析维度（每维=标题+范围说明），不产出任何结论。

- 严禁在本阶段给出命理结论/吉凶判断/预测（付费价值在第二段的正文）
- 维度标题直接贴合用户原话、不用命理术语；维度说明必须是「这一部分会分析…」的范围描述
- 正文（第二段）由解锁端点复用 followup_structured 生成，并用本大纲标题做硬约束

输出 JSON：
{
  "verdict": "一句框架性开场",
  "subtopics": [{"title": "维度标题", "lead": "这一部分会分析…"}]
}
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.ai_service import build_llm_extra_body, get_client, model_pool

logger = logging.getLogger(__name__)

MAX_SUBTOPICS = 6
MIN_SUBTOPICS = 2

_SYSTEM_PROMPT = """你是「趣算算」AI 深度解读的「分析框架」规划助手。

# 你唯一的工作
把用户的问题拆解成一份「分析框架大纲」：告诉用户这份深度解读接下来会从哪几个维度展开。
你**只规划结构，不给结论**。任何命理结论、吉凶判断、预测、数据，都属于后面的正文，本阶段一律不写。

# 输出字段
1. verdict：一句框架性开场，≤40字。只能是「本次深度解读将围绕你的问题，从以下几个维度展开」这类
   转场/说明性表述，**禁止出现任何结论、判断、吉凶、预测、干支/十神/五行等术语**。
2. subtopics：分析维度列表，数量 = 用户问题里独立子问题的个数（2~6 个，不要为凑数强行拆分）。
   每个维度两个字段：
   - title：维度标题。直接引用或微调用户原话，让用户一眼看出在回答他的哪个问题。
     ≤20字，**不使用任何命理术语**（干支、十神、五行、用神、大运、流年等一律不出现）。
     例：「11月入职新公司的整体结果判断」「负债压力的缓解时间与关键转折点」。
   - lead：这一维度的范围说明，1 句，≤45字。必须以「这一部分会分析…」或「这一部分会说明…」
     **起头**，只描述"要分析什么"，绝不给出结论。
     例：「这一部分会分析11月能否顺利入职，并说明入职流程各环节的推进情况。」

# 绝对红线
- 不写任何结论、吉凶、成败、时间点的断言
- 不出现命理术语；不出现「大吉/大凶/一定/注定/必然」等词
- 不编造用户没问、也没提供信息的具体人事细节

只输出一个 JSON 对象，不要解释、不要 Markdown 代码块：
{{"verdict": "...", "subtopics": [{{"title": "...", "lead": "这一部分会分析..."}}]}}"""


def _strip_code_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _fallback_outline(question: str) -> Dict[str, Any]:
    """LLM 不可用时的兜底大纲：按标点切分用户问题，拆成若干维度。"""
    parts = [p.strip() for p in re.split(r"[，。；？！?;,.!\n]+", question or "") if p.strip()]
    # 过短的碎片合并，避免维度过于琐碎
    titles = [p[:20] for p in parts if len(p) >= 4][:MAX_SUBTOPICS]
    if not titles:
        titles = ["你的问题整体情况"]
    subtopics = [
        {"title": t, "lead": f"这一部分会分析「{t}」的具体情况。"}
        for t in titles[:MAX_SUBTOPICS]
    ]
    if len(subtopics) < MIN_SUBTOPICS:
        subtopics.append({
            "title": "整体建议与注意事项",
            "lead": "这一部分会给出与你的问题相关的整体建议与需要注意的地方。",
        })
    return {
        "verdict": "本次深度解读会围绕你的问题，从以下几个维度展开。",
        "subtopics": subtopics,
    }


def _normalize_outline(raw: Dict[str, Any], question: str) -> Dict[str, Any]:
    """归整 LLM 输出：裁剪维度数量、保证字段齐全、去掉越界内容。"""
    verdict = str(raw.get("verdict") or "").strip()
    if not verdict:
        verdict = "本次深度解读会围绕你的问题，从以下几个维度展开。"

    items = raw.get("subtopics") or []
    subtopics: List[Dict[str, str]] = []
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            lead = str(it.get("lead") or "").strip()
            if not title:
                continue
            if not lead:
                lead = f"这一部分会分析「{title}」的具体情况。"
            subtopics.append({"title": title[:30], "lead": lead[:80]})
    if len(subtopics) < MIN_SUBTOPICS:
        return _fallback_outline(question)
    return {"verdict": verdict[:60], "subtopics": subtopics[:MAX_SUBTOPICS]}


async def generate_outline(
    user_question: str,
    history: List[dict],
    gender_cn: str = "",
    age: Optional[int] = None,
    usage_holder: Optional[dict] = None,
) -> Dict[str, Any]:
    """生成「分析框架大纲」。失败时降级为规则兜底，不抛异常。

    usage_holder: 可选 dict，用于回填用量信息供调用方落库。
    """
    user_payload = f"【用户问题】{user_question}\n"
    if gender_cn:
        user_payload += f"【档案性别】{gender_cn}\n"
    if age is not None:
        user_payload += f"【档案年龄】{age}岁\n"
    # 近几轮历史仅作语境参考，避免框架脱离上下文
    recent = [m for m in (history or []) if m.get("role") == "user"][-2:]
    for m in recent:
        q = str(m.get("content") or "").strip()
        if q and q != user_question:
            user_payload += f"【此前提问】{q[:60]}\n"

    if not model_pool:
        logger.warning("[深度解读] 模型池为空，使用兜底大纲")
        return _fallback_outline(user_question)

    try:
        model_config = model_pool[0]
        client = await get_client(model_config)
        resp = await client.chat.completions.create(
            model=model_config.name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.6,
            max_tokens=800,
            response_format={"type": "json_object"},
            timeout=40,
            extra_body=build_llm_extra_body(model_config.name),
        )
        content = _strip_code_fence(resp.choices[0].message.content or "")
        raw = json.loads(content) if content else {}
        if usage_holder is not None:
            usage_holder["success"] = True
            usage_holder["model"] = model_config.name
            u = getattr(resp, "usage", None)
            usage_holder["input_tokens"] = getattr(u, "prompt_tokens", 0) or 0
            usage_holder["output_tokens"] = getattr(u, "completion_tokens", 0) or 0
            usage_holder["total_tokens"] = getattr(u, "total_tokens", 0) or 0
        return _normalize_outline(raw, user_question)
    except Exception as e:
        logger.error(f"[深度解读] 大纲生成失败，降级兜底: {type(e).__name__}: {e}")
        if usage_holder is not None:
            usage_holder["success"] = False
        return _fallback_outline(user_question)
