"""
每日运势 API

GET /api/daily/fortune —— 返回指定档案某一天的运势与「今日建议」。

契约（《今日建议文案口径Spec》第四节 + 第十节命名契约）：
- 字段全英文 snake_case，枚举全英文 token
- 算法 judge 不外露，只暴露 grade ∈ {good, neutral, caution}
"""

import logging
from datetime import date as _date
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.db.session import get_db
from app.models.person import Person
from app.models.user import User
from app.services.daily_fortune_service import generate_daily_fortune
from app.services.feature_flag_service import require_v3_enabled

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/daily", tags=["daily"])


# ============================================================
# 响应模型（前端 src/api/daily.ts 的镜像基准）
# ============================================================

class Advice(BaseModel):
    action: str      # 主行动句，≤20 字，零术语
    basis: str       # 依据句，≤30 字，白话
    chart_ref: str   # 依据行，≤20 字，术语仅此出现，与 source 一致


class FortuneSource(BaseModel):
    liuri_ganzhi: str    # 流日干支，如 "辛丑"
    liuyue_ganzhi: str   # 流月干支，如 "戊戌"
    dayun_ganzhi: str    # 当前大运干支，如 "癸卯"
    shishen_tian: str    # 流日天干十神
    shishen_di: str      # 流日地支十神
    day_master: str      # 日主，如 "辛金"


class DailyFortuneResponse(BaseModel):
    date: str                  # YYYY-MM-DD
    advice: Advice
    source: FortuneSource
    grade: str                 # good | neutral | caution
    yi: List[str]              # 宜，2~3 个短标签
    ji: List[str]              # 忌，1~2 个短标签
    pressure_level: int        # 0~100


class DailyRhythmResponse(BaseModel):
    date: str
    energy_state: str          # smooth | steady | contracting
    suitable: List[str]
    notice: List[str]
    action: str
    basis: str
    chart_ref: str
    pressure_level: int
    source: FortuneSource


# ============================================================
# 当日缓存：同一天同一档案不重复调 LLM
# ============================================================

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_MAX_ENTRIES = 500


def _cache_key(user_id: int, person_id: int, date_str: str) -> str:
    return f"{user_id}:{person_id}:{date_str}"


def _cache_prune(today: str) -> None:
    """只保留当日缓存，避免进程内累积历史结果。"""
    if len(_CACHE) <= _CACHE_MAX_ENTRIES:
        return
    for key in [k for k in _CACHE if not k.endswith(today)]:
        _CACHE.pop(key, None)


def _validate_date(date_str: str) -> str:
    try:
        return _date.fromisoformat(date_str).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="date 需为 YYYY-MM-DD 格式")


def _rhythm_safe_text(value: str, fallback: str) -> str:
    blocked = ("吉", "凶", "宜", "忌", "算命", "改运", "化解")
    return fallback if any(term in (value or "") for term in blocked) else value


@router.get("/fortune", response_model=DailyFortuneResponse)
async def get_daily_fortune(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    person_id: Annotated[int, Query(gt=0, description="档案 ID")],
    date: Annotated[Optional[str], Query(description="YYYY-MM-DD，默认服务器当日")] = None,
):
    target_date = _validate_date(date) if date else _date.today().isoformat()

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise ResourceNotFound("档案不存在")
    if person.user_id != current_user.id:
        raise PermissionDenied("无权访问")

    cache_key = _cache_key(current_user.id, person.id, target_date)
    cached = _CACHE.get(cache_key)
    if cached:
        return cached

    # 旧数据兼容：档案未持久化排盘数据时先补齐（与 person API 同一处理方式）
    bazi_data = person.bazi_data_json
    if not bazi_data:
        from app.skills.orchestrator import generate_full_analysis

        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        await db.commit()

    try:
        fortune = await generate_daily_fortune(
            bazi_data=bazi_data,
            date_str=target_date,
            birth_date=person.birth_date,
        )
    except ValueError as e:
        # 排盘数据不完整等可预期错误，交给前端提示
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[日运] 生成失败 person_id={person_id} date={target_date}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="运势生成失败，请稍后重试")

    _cache_prune(_date.today().isoformat())
    _CACHE[cache_key] = fortune
    return fortune


@router.get("/rhythm", response_model=DailyRhythmResponse)
async def get_daily_rhythm(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    person_id: Annotated[int, Query(gt=0, description="档案 ID")],
    date: Annotated[Optional[str], Query(description="YYYY-MM-DD，默认服务器当日")] = None,
):
    await require_v3_enabled()
    fortune = await get_daily_fortune(
        db=db,
        current_user=current_user,
        person_id=person_id,
        date=date,
    )
    grade = fortune["grade"] if isinstance(fortune, dict) else fortune.grade
    advice = fortune["advice"] if isinstance(fortune, dict) else fortune.advice
    source = fortune["source"] if isinstance(fortune, dict) else fortune.source
    return DailyRhythmResponse(
        date=fortune["date"] if isinstance(fortune, dict) else fortune.date,
        energy_state={
            "good": "smooth",
            "neutral": "steady",
            "caution": "contracting",
        }.get(grade, "steady"),
        suitable=fortune["yi"] if isinstance(fortune, dict) else fortune.yi,
        notice=fortune["ji"] if isinstance(fortune, dict) else fortune.ji,
        action=_rhythm_safe_text(
            advice["action"] if isinstance(advice, dict) else advice.action,
            "今天先稳住节奏，完成计划内最重要的一件事。",
        ),
        basis=_rhythm_safe_text(
            advice["basis"] if isinstance(advice, dict) else advice.basis,
            "今天更适合专注、整理和照顾自己的状态。",
        ),
        chart_ref=_rhythm_safe_text(
            advice["chart_ref"] if isinstance(advice, dict) else advice.chart_ref,
            "基于当日节奏与命盘关系",
        ),
        pressure_level=(
            fortune["pressure_level"] if isinstance(fortune, dict) else fortune.pressure_level
        ),
        source=source,
    )
