import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person
from app.schemas.chart_snapshot_schema import (
    BirthProfileSnapshot,
    ChartSnapshot,
    DayMasterSnapshot,
    PillarSnapshot,
    StrengthSnapshot,
)
from app.skills.orchestrator import generate_full_analysis


CHART_SNAPSHOT_VERSION = "1.0"

_ELEMENT_MAP = {
    "木": "wood",
    "火": "fire",
    "土": "earth",
    "金": "metal",
    "水": "water",
}
_YANG_STEMS = set("甲丙戊庚壬")
_YIN_STEMS = set("乙丁己辛癸")
_TEN_GOD_POSITION_MAP = {
    "年干": "year_stem",
    "月干": "month_stem",
    "日干": "day_stem",
    "时干": "hour_stem",
}
_KEY_MAP = {
    "类型": "type",
    "来源": "source",
    "喜忌": "element_preferences",
    "喜": "favorable",
    "忌": "unfavorable",
    "描述": "description",
    "破格": "break_pattern",
    "总分": "total_score",
    "得令": "season_support",
    "得地": "root_support",
    "得势": "overall_support",
    "细节": "detail",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def calculate_source_hash(person: Person, bazi_data: Mapping[str, Any]) -> str:
    source = {
        "birth_date": person.birth_date,
        "birth_time": person.birth_time,
        "birth_location": person.birth_location,
        "birth_lat": person.birth_lat,
        "birth_lng": person.birth_lng,
        "calendar_type": person.calendar_type,
        "gender": person.gender,
        "bazi_data": bazi_data,
    }
    digest = hashlib.sha256(_canonical_json(source).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _normalize_nested_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            _KEY_MAP.get(str(key), str(key)): _normalize_nested_keys(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_nested_keys(item) for item in value]
    return value


def _extract_elements(*values: Any) -> List[str]:
    elements: List[str] = []
    for value in values:
        text = _canonical_json(value) if isinstance(value, (dict, list)) else str(value or "")
        for char, element in _ELEMENT_MAP.items():
            if char in text and element not in elements:
                elements.append(element)
    return elements


def _parse_pillars(raw: Any) -> Dict[str, PillarSnapshot]:
    values = str(raw or "").replace("，", " ").split()
    positions = ("year", "month", "day", "hour")
    pillars: Dict[str, PillarSnapshot] = {}
    for index, position in enumerate(positions):
        token = values[index] if index < len(values) else ""
        pillars[position] = PillarSnapshot(
            stem=token[:1],
            branch=token[1:2],
        )
    return pillars


def _parse_day_master(raw: Any, pillars: Mapping[str, PillarSnapshot]) -> DayMasterSnapshot:
    text = str(raw or "")
    stem = text[:1] or pillars["day"].stem
    element = next((mapped for char, mapped in _ELEMENT_MAP.items() if char in text), "unknown")
    if element == "unknown":
        stem_element = {
            "甲": "wood", "乙": "wood", "丙": "fire", "丁": "fire", "戊": "earth",
            "己": "earth", "庚": "metal", "辛": "metal", "壬": "water", "癸": "water",
        }
        element = stem_element.get(stem, "unknown")
    yin_yang = "yang" if stem in _YANG_STEMS else "yin" if stem in _YIN_STEMS else "unknown"
    return DayMasterSnapshot(stem=stem, element=element, yin_yang=yin_yang)


def _parse_ten_gods(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return _normalize_nested_keys(raw)
    result: Dict[str, Any] = {}
    for item in str(raw or "").replace("，", "、").split("、"):
        item = item.strip()
        if not item:
            continue
        matched = False
        for prefix, key in _TEN_GOD_POSITION_MAP.items():
            if item.startswith(prefix):
                result[key] = item[len(prefix):]
                matched = True
                break
        if not matched:
            result.setdefault("raw", []).append(item)
    return result


def _cycle_list(source: Mapping[str, Any], keys: Iterable[str]) -> List[Dict[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [
                _normalize_nested_keys(item) if isinstance(item, dict) else {"value": item}
                for item in value
            ]
    return []


def build_chart_snapshot(person: Person, bazi_data: Mapping[str, Any]) -> ChartSnapshot:
    pillars = _parse_pillars(bazi_data.get("四柱"))
    strength_detail = bazi_data.get("旺衰详情")
    strength_score = 0
    if isinstance(strength_detail, dict):
        strength_score = strength_detail.get("总分", 0) or 0
    strength_source = str(bazi_data.get("旺衰结论") or "")
    if "旺" in strength_source:
        strength_level = "strong"
    elif "弱" in strength_source:
        strength_level = "weak"
    elif "平" in strength_source or "中和" in strength_source:
        strength_level = "balanced"
    else:
        strength_level = "unknown"

    pattern_detail = bazi_data.get("格局详情")
    pattern = {
        "name": str(bazi_data.get("格局") or ""),
        "detail": _normalize_nested_keys(pattern_detail) if pattern_detail else {},
    }

    return ChartSnapshot(
        version=CHART_SNAPSHOT_VERSION,
        generated_at=datetime.utcnow(),
        birth_profile=BirthProfileSnapshot(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            gender=person.gender,
            location=person.birth_location,
            latitude=person.birth_lat,
            longitude=person.birth_lng,
            calendar_type=person.calendar_type,
        ),
        pillars=pillars,
        day_master=_parse_day_master(bazi_data.get("日主"), pillars),
        ten_gods=_parse_ten_gods(bazi_data.get("十神分布")),
        strength=StrengthSnapshot(
            level=strength_level,
            score=float(strength_score),
            source=strength_source,
        ),
        useful_elements=_extract_elements(bazi_data.get("用神"), bazi_data.get("喜神")),
        unfavorable_elements=_extract_elements(bazi_data.get("忌神")),
        pattern=pattern,
        luck_cycles=_cycle_list(bazi_data, ("大运列表", "大运")),
        annual_cycles=_cycle_list(bazi_data, ("重点流年", "流年列表", "流年数据")),
        monthly_cycles=_cycle_list(bazi_data, ("流月列表", "流月数据", "月运")),
        source_hash=calculate_source_hash(person, bazi_data),
    )


async def get_or_create_chart_snapshot(
    db: AsyncSession,
    person: Person,
) -> ChartSnapshot:
    bazi_data = person.bazi_data_json
    if not bazi_data:
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data

    source_hash = calculate_source_hash(person, bazi_data)
    stored = person.chart_snapshot_json
    if (
        stored
        and person.chart_snapshot_version == CHART_SNAPSHOT_VERSION
        and stored.get("source_hash") == source_hash
    ):
        return ChartSnapshot.model_validate(stored)

    snapshot = build_chart_snapshot(person, bazi_data)
    person.chart_snapshot_json = snapshot.model_dump(mode="json")
    person.chart_snapshot_version = CHART_SNAPSHOT_VERSION
    person.chart_snapshot_updated_at = datetime.utcnow()
    await db.flush()
    return snapshot
