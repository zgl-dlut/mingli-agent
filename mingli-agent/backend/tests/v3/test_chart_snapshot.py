from copy import deepcopy

from app.models.person import Person
from app.services.chart_snapshot_service import (
    CHART_SNAPSHOT_VERSION,
    build_chart_snapshot,
    calculate_source_hash,
)


def _person() -> Person:
    return Person(
        user_id=1,
        name="小玲",
        gender="female",
        birth_date="1992-08-08",
        birth_time="10:30",
        birth_location="辽宁省大连市",
        birth_lat=38.914,
        birth_lng=121.614,
        calendar_type="solar",
        province="辽宁省",
        city="大连市",
    )


def _bazi_data():
    return {
        "四柱": "壬申 戊申 庚申 辛巳",
        "日主": "庚金（阳金）",
        "十神分布": "年干食神、月干偏印、日干日主、时干劫财",
        "旺衰结论": "身旺",
        "旺衰详情": {"总分": 4},
        "用神": "火",
        "喜神": "木",
        "忌神": "金、土",
        "格局": "偏印格",
        "格局详情": {"类型": "偏印格", "来源": "月令申"},
        "大运列表": [{"ganzhi": "丁未", "start_year": "2022", "end_year": "2031"}],
        "重点流年": [{"year": 2027, "ganzhi": "丁未"}],
    }


def test_snapshot_contract_and_mapping():
    snapshot = build_chart_snapshot(_person(), _bazi_data())

    assert snapshot.version == CHART_SNAPSHOT_VERSION
    assert snapshot.pillars["day"].stem == "庚"
    assert snapshot.pillars["day"].branch == "申"
    assert snapshot.day_master.stem == "庚"
    assert snapshot.day_master.element == "metal"
    assert snapshot.day_master.yin_yang == "yang"
    assert snapshot.ten_gods["year_stem"] == "食神"
    assert snapshot.strength.level == "strong"
    assert snapshot.strength.score == 4
    assert snapshot.useful_elements == ["fire", "wood"]
    assert snapshot.unfavorable_elements == ["earth", "metal"]
    assert snapshot.pattern["detail"]["type"] == "偏印格"
    assert snapshot.luck_cycles[0]["ganzhi"] == "丁未"

    payload = snapshot.model_dump(mode="json")
    assert set(payload) == {
        "version",
        "generated_at",
        "birth_profile",
        "pillars",
        "day_master",
        "ten_gods",
        "strength",
        "useful_elements",
        "unfavorable_elements",
        "pattern",
        "luck_cycles",
        "annual_cycles",
        "monthly_cycles",
        "source_hash",
    }


def test_source_hash_is_deterministic_and_invalidates_on_source_change():
    person = _person()
    source = _bazi_data()

    first = calculate_source_hash(person, source)
    second = calculate_source_hash(person, deepcopy(source))
    assert first == second

    changed = deepcopy(source)
    changed["四柱"] = "壬申 戊申 辛酉 辛巳"
    assert calculate_source_hash(person, changed) != first

    person.birth_time = "11:30"
    assert calculate_source_hash(person, source) != first
