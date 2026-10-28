from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety_event import SafetyEvent


CRISIS_REPLY = (
    "我先退出命局人格的角色。你刚才的表达可能意味着你正处在很难承受的时刻。"
    "请立即联系身边可信任的人陪着你，并拨打 120、110 或当地心理援助热线。"
    "如果你已经准备伤害自己，请远离可能造成伤害的物品并立即前往最近的急诊。"
)
_CRISIS_TERMS = (
    "不想活",
    "想死",
    "自杀",
    "结束生命",
    "伤害自己",
    "割腕",
    "跳楼",
    "活着没意思",
)
_OUTPUT_VIOLATIONS = (
    "我是真人",
    "我就在你身边",
    "只有我懂你",
    "不要告诉任何人",
    "一定会发生",
    "保证能",
)


def detect_input_safety(content: str) -> Optional[str]:
    normalized = content.replace(" ", "").lower()
    if any(term in normalized for term in _CRISIS_TERMS):
        return "crisis"
    return None


def filter_persona_output(content: str) -> tuple[str, Optional[str]]:
    if any(term in content for term in _OUTPUT_VIOLATIONS):
        return (
            "我不能把自己描述成现实中的真人，也不能替你作确定性承诺。"
            "我们可以继续基于你提供的事实，一起把眼前的问题梳理清楚。",
            "output_violation",
        )
    return content, None


async def record_safety_event(
    db: AsyncSession,
    user_id: int,
    category: str,
    action: str,
    persona_id: int | None = None,
    conversation_id: int | None = None,
    metadata: dict | None = None,
) -> SafetyEvent:
    event = SafetyEvent(
        user_id=user_id,
        persona_id=persona_id,
        conversation_id=conversation_id,
        category=category,
        action=action,
        metadata_json=metadata,
    )
    db.add(event)
    await db.flush()
    return event
