from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import V3APIError
from app.models.person import Person
from app.models.persona import Persona
from app.services.chart_snapshot_service import get_or_create_chart_snapshot
from app.services.report_service import get_owned_person


PERSONA_PROMPT_VERSION = "v3-persona-1"
_AVATAR_KEYS = {
    "甲": "jia-wood",
    "乙": "yi-wood",
    "丙": "bing-fire",
    "丁": "ding-fire",
    "戊": "wu-earth",
    "己": "ji-earth",
    "庚": "geng-metal",
    "辛": "xin-metal",
    "壬": "ren-water",
    "癸": "gui-water",
}
_ELEMENT_TRAITS = {
    "wood": ["重视成长", "愿意探索", "在行动中建立方向"],
    "fire": ["表达直接", "重视连接", "容易被真实反馈点亮"],
    "earth": ["看重稳定", "习惯承担", "倾向先解决现实问题"],
    "metal": ["判断清晰", "重视边界", "偏好直接而有依据的表达"],
    "water": ["感受细腻", "善于观察", "需要留出思考空间"],
    "unknown": ["保持观察", "重视现实反馈", "愿意一起梳理问题"],
}


def age_on(birth_date: str, today: date | None = None) -> int:
    born = date.fromisoformat(birth_date[:10])
    current = today or date.today()
    return current.year - born.year - ((current.month, current.day) < (born.month, born.day))


async def create_or_get_persona(
    db: AsyncSession,
    user_id: int,
    person_id: int,
    name: str | None = None,
) -> tuple[Persona, bool]:
    if not settings.V3_ENABLED:
        raise V3APIError(403, "feature_disabled", "V3 功能尚未开放")
    if not settings.PERSONA_ENABLED:
        raise V3APIError(403, "feature_disabled", "命局人格尚未开放")
    person = await get_owned_person(db, person_id, user_id)
    existing = (
        await db.execute(select(Persona).where(Persona.person_id == person_id))
    ).scalar_one_or_none()
    if existing:
        return existing, False
    if not person.is_self or person.relationship_type != "self":
        raise V3APIError(
            403,
            "self_profile_required",
            "首发仅支持为本人档案创建命局人格",
            metric="persona_profile",
        )
    if age_on(person.birth_date) < 18:
        raise V3APIError(
            403,
            "minor_not_allowed",
            "未成年人暂不开放命局人格",
            metric="persona_profile",
        )

    snapshot = await get_or_create_chart_snapshot(db, person)
    element = snapshot.day_master.element
    profile = {
        "day_master": snapshot.day_master.model_dump(),
        "tone": "直接、克制、温和，不使用分节报告口吻",
        "traits": _ELEMENT_TRAITS.get(element, _ELEMENT_TRAITS["unknown"]),
        "boundaries": [
            "不冒充真人",
            "不作宿命断言",
            "不提供医疗、法律或高风险财务结论",
        ],
    }
    persona = Persona(
        user_id=user_id,
        person_id=person_id,
        name=(name or f"{person.name}的命局人格").strip()[:100],
        avatar_key=_AVATAR_KEYS.get(snapshot.day_master.stem, "default"),
        profile_json=profile,
        prompt_version=PERSONA_PROMPT_VERSION,
    )
    try:
        async with db.begin_nested():
            db.add(persona)
            await db.flush()
    except IntegrityError:
        existing = (
            await db.execute(select(Persona).where(Persona.person_id == person_id))
        ).scalar_one()
        return existing, False
    await db.commit()
    return persona, True
