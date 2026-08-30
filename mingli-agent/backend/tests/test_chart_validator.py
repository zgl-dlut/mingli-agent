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
    # key_liunian 空列表时 _format_key_liunian 返回骨架文本（含"暂无"，LLM 不会编造）
    assert "暂无" in ctx["key_liunian"]
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


# ============================================================
# 首次报告 prompt 缓存友好布局测试
# 静态规则前置、动态"用户输入数据"统一收尾，形成可缓存公共前缀
# ============================================================

def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def test_first_reading_static_prefix_stable():
    """不同命盘构建的 prompt，静态公共前缀足够长（命盘数据在尾部，不破坏前缀）"""
    c1 = _full_chart()
    c2 = _full_chart()
    c2["日主"] = "壬水（江河之水）"
    c2["四柱"] = "壬申 庚戌 壬子 辛亥"
    c2["用神"] = "金水"
    c2["忌神"] = "火土"
    c2["重点流年"] = [{"year": "2028", "ganzhi": "戊申", "judge": "吉", "reason": "金助身"}]

    # 同年龄段（同为成人），保证 age_stage 模板分支一致，前缀可比
    p1 = build_first_reading_structured_prompt(c1, "男", "1990-11-10", "08:00", "北京")
    p2 = build_first_reading_structured_prompt(c2, "女", "1990-11-10", "08:00", "上海")

    prefix_len = _common_prefix_len(p1, p2)
    # 静态规则区（角色/任务/输出格式/硬性规范）应全部命中缓存，阈值取 5000 字
    assert prefix_len >= 5000, f"首次报告静态公共前缀仅{prefix_len}字，缓存收益受限"
    print(f"✓ test_first_reading_static_prefix_stable (公共前缀={prefix_len}字)")


def test_first_reading_dynamic_data_at_tail():
    """动态"用户输入数据"区块位于 prompt 尾部，不切断静态前缀"""
    prompt = build_first_reading_structured_prompt(
        _full_chart(), "男", "1990-11-10", "08:00", "北京"
    )
    data_pos = prompt.index("# 用户输入数据")
    rule_pos = prompt.index("# 文风、字数、格式硬性规范")
    # 动态数据区在所有静态规则之后
    assert data_pos > rule_pos, "用户输入数据未移到尾部，会切断缓存前缀"
    # 命盘数据（日主/四柱）应出现在尾部数据区内
    assert prompt.index("【日主五行】") > rule_pos
    print("✓ test_first_reading_dynamic_data_at_tail")


def test_first_reading_yongshen_ref_moved():
    """用神/忌神不再内联注入模板，改为引用文末数据（保证模板静态）"""
    prompt = build_first_reading_structured_prompt(
        _full_chart(), "男", "1990-11-10", "08:00", "北京"
    )
    # 模板内改为静态引用措辞，不再硬编码具体用神忌神值
    assert "具体取值见文末" in prompt
    assert "明确标注用神（木）和忌神（水）" not in prompt
    print("✓ test_first_reading_yongshen_ref_moved")


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
    test_first_reading_static_prefix_stable()
    test_first_reading_dynamic_data_at_tail()
    test_first_reading_yongshen_ref_moved()
    print("=" * 60)
    print("全部测试通过")
