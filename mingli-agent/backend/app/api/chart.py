"""
命盘 API

GET /api/chart/{person_id}?year=&month= —— 返回指定档案的完整命盘：
生辰信息 + 四柱排盘 + 命理分析 + 大运 + 流年/流月/流日三级数据。

命名契约（与《今日建议文案口径Spec》一致）：
- 传输层字段一律英文 snake_case，枚举一律英文小写 token
  （position: year/month/day/hour；grade: good/neutral/caution；gender: male/female）
- 命理术语值（干支/十神/五行/纳音/神煞/长生/格局）保持中文，必须与算法输出逐字一致
- 算法 judge 的 5 档（大吉/吉/平/凶/大凶）不外露，只暴露 grade
"""

import calendar
import logging
from datetime import datetime
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.db.session import get_db
from app.models.person import Person
from app.models.user import User
from app.services.bazi_service import (
    calculate_bazi,
    calculate_shishen,
    calculate_true_solar_time,
    get_zodiac,
    normalize_gender,
)
from app.services.daily_fortune_service import _calc_age, map_grade, parse_pillars
from app.skills.divination.dayun_liunian_skill import analyze_liunian, analyze_liuyue
from app.skills.divination.liuri_skill import analyze_liuri, year_to_ganzhi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chart", tags=["chart"])

# 四柱柱位：中文键 → 对外英文 token（顺序即展示顺序：年月日时）
POSITION_MAP = [("年", "year"), ("月", "month"), ("日", "day"), ("时", "hour")]


# ============================================================
# 响应模型（前端 src/api/chart.ts 的镜像基准）
# ============================================================

class ChartProfile(BaseModel):
    name: str
    gender: str                # male | female
    birth_date: str            # YYYY-MM-DD
    birth_time: str            # HH:MM
    birth_location: str
    calendar_type: str         # solar | lunar
    zodiac: str                # 生肖（中文）
    solar_time: str            # 真太阳时校正后的时刻 YYYY-MM-DD HH:MM


class CangganItem(BaseModel):
    gan: str
    shishen: str


class Pillar(BaseModel):
    position: str              # year | month | day | hour
    gan: str
    zhi: str
    gan_shishen: str           # 日柱为「日主」
    canggan: List[CangganItem]
    nayin: str
    changsheng: str
    shensha: List[str]


class ChartGrid(BaseModel):
    pillars: List[Pillar]
    wuxing_count: Dict[str, int]
    kongwang: List[str]
    tiangan_he: List[str]


class ChartAnalysis(BaseModel):
    day_master: str
    yueling: str
    wangshuai: str
    geju: str
    yongshen: str
    xishen: str
    jishen: str
    tiaohou: str
    motto: str


class DayunItem(BaseModel):
    ganzhi: str
    start_year: int
    end_year: int
    start_age: int
    is_current: bool


class DayunBlock(BaseModel):
    direction: str             # 顺 | 逆
    start_age: float
    list: List[DayunItem]


class LiunianItem(BaseModel):
    year: int
    ganzhi: str
    age: Optional[int]
    grade: str                 # good | neutral | caution
    is_yongshen: bool
    is_jishen: bool
    interactions: List[str]


class LiuyueItem(BaseModel):
    solar_month: int
    ganzhi: str
    grade: str
    is_yongshen: bool
    is_jishen: bool
    shishen_tian: str
    shishen_di: str


class LiuriItem(BaseModel):
    date: str                  # YYYY-MM-DD
    ganzhi: str
    shishen_tian: str
    shishen_di: str
    grade: str
    is_yongshen: bool
    is_jishen: bool


class ChartResponse(BaseModel):
    person_id: int
    year: int
    month: str                 # YYYY-MM
    profile: ChartProfile
    chart: ChartGrid
    analysis: ChartAnalysis
    dayun: DayunBlock
    liunian: List[LiunianItem]
    liuyue: List[LiuyueItem]
    liuri: List[LiuriItem]


# ============================================================
# 组装工具
# ============================================================

def _build_pillars(chart, day_tian: str) -> List[Pillar]:
    """把 calculate_bazi 的输出组装为对外排盘网格。"""
    result: List[Pillar] = []
    for cn, token in POSITION_MAP:
        p = chart.pillars.get(cn, {})
        canggan = [
            CangganItem(gan=g, shishen=calculate_shishen(day_tian, g))
            for g in (chart.canggan.get(cn) or [])
        ]
        result.append(
            Pillar(
                position=token,
                gan=str(p.get("tian", "")),
                zhi=str(p.get("di", "")),
                gan_shishen=str((chart.shishen.get(cn) or {}).get("tian", "")),
                canggan=canggan,
                nayin=str((chart.nayin or {}).get(cn, "")),
                changsheng=str((chart.changsheng or {}).get(cn, "")),
                shensha=list((chart.shensha or {}).get(cn, []) or []),
            )
        )
    return result


def _build_dayun(chart, birth_year: int, current_year: int) -> DayunBlock:
    """大运列表：起运年龄按「该步起始年 - 出生年」换算，标注当前所处大运。"""
    items: List[DayunItem] = []
    for d in chart.dayun or []:
        try:
            start_year = int(d.start_year)
            end_year = int(d.end_year)
        except (TypeError, ValueError):
            continue
        items.append(
            DayunItem(
                ganzhi=str(d.ganzhi or ""),
                start_year=start_year,
                end_year=end_year,
                start_age=start_year - birth_year,
                is_current=start_year <= current_year <= end_year,
            )
        )
    return DayunBlock(
        direction=str(chart.dayun_direction or ""),
        start_age=round(float(chart.start_age), 1) if chart.start_age is not None else 0.0,
        list=items,
    )


def _dayun_ganzhi_for_year(dayun_items: List[DayunItem], year: int) -> str:
    """取该年份所处大运干支；未起运时返回空串。"""
    for item in dayun_items:
        if item.start_year <= year <= item.end_year:
            return item.ganzhi
    return ""


def _build_liunian(
    year: int, dayun_items: List[DayunItem], day_tian: str, pillars: Dict,
    yongshen: str, jishen: str, is_strong: bool, birth_date: str,
) -> List[LiunianItem]:
    """选中流年所属大运覆盖的整段 10 年。"""
    window: Optional[DayunItem] = next(
        (d for d in dayun_items if d.start_year <= year <= d.end_year), None,
    )
    if window:
        years = list(range(window.start_year, window.end_year + 1))
    else:
        # 未起运（幼年）或超出大运范围：以选中年份为中心取 10 年
        years = list(range(year - 4, year + 6))

    result: List[LiunianItem] = []
    for y in years:
        ganzhi = year_to_ganzhi(y)
        # analyze_liunian 依赖大运干支做互动分析，空串会取值越界；
        # 未起运/超出大运范围时回落到首步大运，仍无则输出中性占位。
        dayun_ganzhi = _dayun_ganzhi_for_year(dayun_items, y)
        if not dayun_ganzhi and dayun_items:
            dayun_ganzhi = dayun_items[0].ganzhi
        if not dayun_ganzhi:
            result.append(
                LiunianItem(
                    year=y,
                    ganzhi=ganzhi,
                    age=_calc_age(birth_date, f"{y}-12-31"),
                    grade="neutral",
                    is_yongshen=False,
                    is_jishen=False,
                    interactions=[],
                )
            )
            continue

        analysis = analyze_liunian(
            liunian_ganzhi=ganzhi,
            dayun_ganzhi=dayun_ganzhi,
            day_tian=day_tian,
            pillars=pillars,
            yongshen=yongshen,
            jishen=jishen,
            is_strong=is_strong,
        )
        result.append(
            LiunianItem(
                year=y,
                ganzhi=ganzhi,
                age=_calc_age(birth_date, f"{y}-12-31"),
                grade=map_grade(analysis.get("overall_judge", "")),
                is_yongshen=bool(analysis.get("is_yongshen")),
                is_jishen=bool(analysis.get("is_jishen")),
                interactions=list(analysis.get("interactions") or []),
            )
        )
    return result


def _build_liuyue(
    year: int, day_tian: str, pillars: Dict,
    yongshen: str, jishen: str, is_strong: bool,
) -> List[LiuyueItem]:
    """选中流年的 12 个流月（1 月属上一流年，与算法口径一致）。"""
    months = analyze_liuyue(
        liunian_ganzhi=year_to_ganzhi(year),
        day_tian=day_tian,
        pillars=pillars,
        yongshen=yongshen,
        jishen=jishen,
        is_strong=is_strong,
    )
    return [
        LiuyueItem(
            solar_month=int(m.get("solar_month", 0)),
            ganzhi=str(m.get("month_ganzhi", "")),
            grade=map_grade(str(m.get("judge", ""))),
            is_yongshen=bool(m.get("is_yongshen")),
            is_jishen=bool(m.get("is_jishen")),
            shishen_tian=str(m.get("shishen_tian", "")),
            shishen_di=str(m.get("shishen_di", "")),
        )
        for m in months
    ]


def _build_liuri(
    year: int, month: int, day_tian: str, pillars: Dict,
    yongshen: str, jishen: str, is_strong: bool,
    dayun_items: List[DayunItem], liuyue_list: List[LiuyueItem],
) -> List[LiuriItem]:
    """选中月份的整月每日流日（用户未指定粒度时按整月列表输出）。"""
    liuyue_ganzhi = ""
    for item in liuyue_list:
        if item.solar_month == month:
            liuyue_ganzhi = item.ganzhi
            break
    dayun_ganzhi = _dayun_ganzhi_for_year(dayun_items, year)

    days_in_month = calendar.monthrange(year, month)[1]
    result: List[LiuriItem] = []
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        analysis = analyze_liuri(
            date_str=date_str,
            day_tian=day_tian,
            pillars=pillars,
            yongshen=yongshen,
            jishen=jishen,
            dayun_ganzhi=dayun_ganzhi,
            liuyue_ganzhi=liuyue_ganzhi,
            is_strong=is_strong,
        )
        result.append(
            LiuriItem(
                date=date_str,
                ganzhi=str(analysis.get("ganzhi", "")),
                shishen_tian=str(analysis.get("shishen_tian", "")),
                shishen_di=str(analysis.get("shishen_di", "")),
                grade=map_grade(str(analysis.get("judge", ""))),
                is_yongshen=bool(analysis.get("is_yongshen")),
                is_jishen=bool(analysis.get("is_jishen")),
            )
        )
    return result


def _validate_month(month: str, year: int) -> str:
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise HTTPException(status_code=400, detail="month 需为 YYYY-MM 格式")
    if parsed.year != year:
        raise HTTPException(status_code=400, detail="month 的年份需与 year 一致")
    return month


# ============================================================
# 路由
# ============================================================

@router.get("/{person_id}", response_model=ChartResponse)
async def get_chart(
    person_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    year: Annotated[Optional[int], Query(description="流年年份，默认当年")] = None,
    month: Annotated[Optional[str], Query(description="流月，YYYY-MM，默认当月")] = None,
):
    now = datetime.now()
    target_year = year or now.year
    target_month = _validate_month(month, target_year) if month else f"{target_year}-{now.month:02d}"

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise ResourceNotFound("档案不存在")
    if person.user_id != current_user.id:
        raise PermissionDenied("无权访问")

    # 旧数据兼容：档案未持久化排盘数据时先补齐（与 daily / person API 同一处理方式）
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
        gender = normalize_gender(person.gender)
        chart = calculate_bazi(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            gender=gender,
        )
    except Exception as e:
        logger.error(f"[命盘] 排盘失败 person_id={person_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="排盘失败，请检查出生信息是否完整")

    pillars = parse_pillars(bazi_data.get("四柱", ""))
    if "日" not in pillars:
        raise HTTPException(status_code=400, detail="档案排盘数据缺少四柱信息")

    day_tian = pillars["日"]["tian"]
    yongshen = str(bazi_data.get("用神") or "")
    jishen = str(bazi_data.get("忌神") or "")
    wangshuai = str(bazi_data.get("旺衰结论") or "")
    is_strong = wangshuai.startswith(("身旺", "身偏旺"))

    birth_year = int(person.birth_date.split("-")[0])
    birth_dt = datetime.strptime(f"{person.birth_date} {person.birth_time}", "%Y-%m-%d %H:%M")
    true_time = calculate_true_solar_time(birth_dt, person.birth_lng)

    dayun_block = _build_dayun(chart, birth_year, now.year)
    liuyue_list = _build_liuyue(
        target_year, day_tian, pillars, yongshen, jishen, is_strong,
    )

    return ChartResponse(
        person_id=person.id,
        year=target_year,
        month=target_month,
        profile=ChartProfile(
            name=person.name,
            gender=gender,
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            birth_location=person.birth_location or "",
            calendar_type=person.calendar_type or "solar",
            zodiac=get_zodiac(birth_year),
            solar_time=true_time.strftime("%Y-%m-%d %H:%M"),
        ),
        chart=ChartGrid(
            pillars=_build_pillars(chart, day_tian),
            wuxing_count=dict(chart.wuxing or {}),
            kongwang=list(chart.kongwang or []),
            tiangan_he=list(chart.tiangan_he or []),
        ),
        analysis=ChartAnalysis(
            day_master=str(bazi_data.get("日主") or ""),
            yueling=str(bazi_data.get("月令") or ""),
            wangshuai=wangshuai,
            geju=str(bazi_data.get("格局") or ""),
            yongshen=yongshen,
            xishen=str(bazi_data.get("喜神") or ""),
            jishen=jishen,
            tiaohou=str(bazi_data.get("调候描述") or ""),
            motto=str(bazi_data.get("命格箴言") or ""),
        ),
        dayun=dayun_block,
        liunian=_build_liunian(
            target_year, dayun_block.list, day_tian, pillars,
            yongshen, jishen, is_strong, person.birth_date,
        ),
        liuyue=liuyue_list,
        liuri=_build_liuri(
            target_year, int(target_month.split("-")[1]), day_tian, pillars,
            yongshen, jishen, is_strong, dayun_block.list, liuyue_list,
        ),
    )
