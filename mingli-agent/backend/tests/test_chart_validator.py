"""命盘数据校验模块单元测试"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.chart_validator import (
    validate_chart_data,
    get_chart_fingerprint,
    MISSING_MARKER,
)
from app.services.skill_prompts import _build_context_vars
from app.services.prompt_builder import build_first_reading_structured_prompt


# 完整命盘数据（基于 generate_full_analysis 返回结构）
def _full_chart():
    return {
        "四柱": "庚午年 丁亥月 丙寅日 壬辰时",
        "日主": "丙火（太阳之火，光明热烈）",
        "月令": "亥月",
        "旺衰结论": "偏弱",
        "旺衰详情": {},
        "格局": "七杀格",
        "格局详情": {},
        "用神": "木",
        "喜神": "火",
        "忌神": "水",
        "调候描述": "调候用木",
        "地支作用": "寅亥合木",
        "十神分布": "偏官旺",
        "五行分布": {"金": 2, "木": 1, "水": 2, "火": 2, "土": 1},
        "纳音": {},
        "当前大运": "癸卯 2020-2029",
        "大运解读": "癸卯运利于学习",
        "重点流年": [
            {"year": "2026", "ganzhi": "丙午", "judge": "吉", "reason": "火助身"},
            {"year": "2027", "ganzhi": "丁未", "judge": "平", "reason": "未土泄火"},
        ],
        "五行应用": {},
        "占星数据": {},
        "生肖": "马",
        "命格箴言": {},
        "命格箴言标签": {},
    }


# ============================================================
# validate_chart_data 测试
# ============================================================

def test_validate_full_chart_passes():
    """完整命盘数据校验通过"""
    ok, missing = validate_chart_data(_full_chart())
    assert ok is True
    assert missing == []
    print("✓ test_validate_full_chart_passes")


def test_validate_empty_dict():
    """空 dict 校验失败，返回'整个命盘数据为空'"""
    ok, missing = validate_chart_data({})
    assert ok is False
    assert "整个命盘数据为空" in missing
    print(f"✓ test_validate_empty_dict (missing={missing})")


def test_validate_none_input():
    """None 输入校验失败"""
    ok, missing = validate_chart_data(None)
    assert ok is False
    assert "整个命盘数据为空" in missing
    print("✓ test_validate_none_input")


def test_validate_non_dict_input():
    """非 dict 输入校验失败"""
    ok, missing = validate_chart_data("不是dict")  # type: ignore
    assert ok is False
    print("✓ test_validate_non_dict_input")


def test_validate_single_field_missing():
    """单字段缺失被检出"""
    chart = _full_chart()
    del chart["日主"]
    ok, missing = validate_chart_data(chart)
    assert ok is False
    assert "日主" in missing
    assert len(missing) == 1
    print("✓ test_validate_single_field_missing")


def test_validate_empty_string_field():
    """空字符串字段被检出"""
    chart = _full_chart()
    chart["用神"] = ""
    ok, missing = validate_chart_data(chart)
    assert ok is False
    assert "用神" in missing
    print("✓ test_validate_empty_string_field")


def test_validate_empty_list_field():
    """空列表字段被检出"""
    chart = _full_chart()
    chart["重点流年"] = []
    ok, missing = validate_chart_data(chart)
    assert ok is False
    assert "重点流年" in missing
    print("✓ test_validate_empty_list_field")


def test_validate_whitespace_string_field():
    """纯空白字符串字段被检出"""
    chart = _full_chart()
    chart["格局"] = "   "
    ok, missing = validate_chart_data(chart)
    assert ok is False
    assert "格局" in missing
    print("✓ test_validate_whitespace_string_field")


# ============================================================
# get_chart_fingerprint 测试
# ============================================================

def test_fingerprint_normal():
    """正常命盘指纹提取"""
    fp = get_chart_fingerprint(_full_chart())
    assert "日主" in fp
    assert "用神" in fp
    assert fp["用神"] == "木"
    print(f"✓ test_fingerprint_normal: {fp}")


def test_fingerprint_empty():
    """空 dict 指纹返回错误标记"""
    fp = get_chart_fingerprint({})
    assert "错误" in fp
    print("✓ test_fingerprint_empty")


def test_fingerprint_none():
    """None 指纹返回错误标记"""
    fp = get_chart_fingerprint(None)  # type: ignore
    assert "错误" in fp
    print("✓ test_fingerprint_none")


# ============================================================
# _build_context_vars 缺失标注测试
# ============================================================

def test_context_vars_full_data():
    """完整数据时 context 无 MISSING_MARKER"""
    ctx = _build_context_vars(
        analysis_data=_full_chart(),
        gender="男",
        user_question="测试问题",
        birth_date="1990-11-10",
    )
    # 8 个必需字段都不应是 MISSING_MARKER
    assert ctx["rizhu"] != MISSING_MARKER
    assert ctx["sizu"] != MISSING_MARKER
    assert ctx["yongshen"] != MISSING_MARKER
    assert ctx["jishen"] != MISSING_MARKER
    assert ctx["wangshuai"] != MISSING_MARKER
    assert ctx["geju_description"] != MISSING_MARKER
    assert ctx["current_dayun"] != MISSING_MARKER
    assert ctx["key_liunian"] != MISSING_MARKER
    print("✓ test_context_vars_full_data")


def test_context_vars_missing_fields_marked():
    """缺失字段时 context 标注 MISSING_MARKER（key_liunian 是"暂无"由 _format_key_liunian 处理）"""
    ctx = _build_context_vars(
        analysis_data={},
        gender="男",
        user_question="测试问题",
        birth_date="1990-11-10",
    )
    # 7 个 str 必需字段应是 MISSING_MARKER
    assert ctx["rizhu"] == MISSING_MARKER
    assert ctx["sizu"] == MISSING_MARKER
    assert ctx["yongshen"] == MISSING_MARKER
    assert ctx["jishen"] == MISSING_MARKER
    assert ctx["wangshuai"] == MISSING_MARKER
    assert ctx["geju_description"] == MISSING_MARKER
    assert ctx["current_dayun"] == MISSING_MARKER
    # key_liunian 空列表时 _format_key_liunian 返回"暂无"（非空，LLM 不会编造）
    assert ctx["key_liunian"] == "暂无"
    print("✓ test_context_vars_missing_fields_marked")


# ============================================================
# build_first_reading_structured_prompt 缺失标注测试
# ============================================================

def test_first_reading_prompt_full_data():
    """完整数据时 prompt 无 MISSING_MARKER"""
    prompt = build_first_reading_structured_prompt(
        _full_chart(), "男", "1990-11-10", "08:00", "北京"
    )
    assert MISSING_MARKER not in prompt
    print("✓ test_first_reading_prompt_full_data")


def test_first_reading_prompt_missing_data_marked():
    """缺失数据时 prompt 出现 MISSING_MARKER"""
    prompt = build_first_reading_structured_prompt(
        {}, "男", "1990-11-10", "08:00", "北京"
    )
    # 至少出现一次 MISSING_MARKER（缺失字段被标注）
    assert MISSING_MARKER in prompt
    print(f"✓ test_first_reading_prompt_missing_data_marked (MISSING_MARKER出现{prompt.count(MISSING_MARKER)}次)")


def test_first_reading_prompt_partial_missing():
    """部分字段缺失时，只有缺失的被标注"""
    chart = _full_chart()
    del chart["日主"]  # 只删日主
    chart["用神"] = ""
    prompt = build_first_reading_structured_prompt(
        chart, "男", "1990-11-10", "08:00", "北京"
    )
    assert MISSING_MARKER in prompt
    print("✓ test_first_reading_prompt_partial_missing")


if __name__ == "__main__":
    print("=" * 60)
    print("命盘数据校验模块测试")
    print("=" * 60)
    test_validate_full_chart_passes()
    test_validate_empty_dict()
    test_validate_none_input()
    test_validate_non_dict_input()
    test_validate_single_field_missing()
    test_validate_empty_string_field()
    test_validate_empty_list_field()
    test_validate_whitespace_string_field()
    test_fingerprint_normal()
    test_fingerprint_empty()
    test_fingerprint_none()
    test_context_vars_full_data()
    test_context_vars_missing_fields_marked()
    test_first_reading_prompt_full_data()
    test_first_reading_prompt_missing_data_marked()
    test_first_reading_prompt_partial_missing()
    print("=" * 60)
    print("全部测试通过")
