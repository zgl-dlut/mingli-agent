"""
排盘容错单元测试（阶段1验证）

验证 generate_full_analysis 的局部容错能力：
1. 基础排盘 calculate_bazi 失败 → 抛 RuntimeError（带上下文）
2. 中间 skill（旺衰/调候/格局）失败 → 不崩溃，对应字段置空，其他字段正常
3. 返回 dict 始终包含完整 key 集合，不会因局部异常变空

mock 策略：patch 源模块函数（orchestrator 函数内 import，patch 模块属性生效）
"""
import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.skills.orchestrator import generate_full_analysis


# 命例：1990-06-15 10:30 男，北京
TEST_CASE = {
    "birth_date": "1990-06-15",
    "birth_time": "10:30",
    "longitude": 116.4,
    "latitude": 39.9,
    "gender": "男",
    "location": "北京",
}

# generate_full_analysis 返回的完整 key 集合（任何容错路径都应保留）
_EXPECTED_KEYS = {
    "四柱", "日主", "月令", "旺衰结论", "旺衰详情", "格局", "格局详情",
    "用神", "喜神", "忌神", "调候描述", "地支作用", "十神分布", "五行分布",
    "纳音", "当前大运", "大运解读", "重点流年", "五行应用", "占星数据",
    "生肖", "命格箴言", "命格箴言标签",
    "大运方向", "起运年龄", "大运列表", "空亡", "长生十二宫", "神煞", "天干五合",
}


def _call():
    return generate_full_analysis(
        birth_date=TEST_CASE["birth_date"],
        birth_time=TEST_CASE["birth_time"],
        longitude=TEST_CASE["longitude"],
        latitude=TEST_CASE["latitude"],
        gender=TEST_CASE["gender"],
        location=TEST_CASE["location"],
    )


# ============================================================
# 1. 基础排盘失败 → 抛 RuntimeError
# ============================================================

def test_calculate_bazi_failure_raises_runtimeerror():
    """calculate_bazi 抛异常时，generate_full_analysis 抛 RuntimeError（带上下文）"""
    with patch("app.services.bazi_service.calculate_bazi", side_effect=ValueError("测试-节气表缺失")):
        with pytest.raises(RuntimeError) as exc_info:
            _call()
        # 异常信息含出生信息和原始异常类型
        assert "基础排盘失败" in str(exc_info.value)
        assert "1990-06-15" in str(exc_info.value)
        assert "ValueError" in str(exc_info.value)
    print("✓ test_calculate_bazi_failure_raises_runtimeerror")


# ============================================================
# 2. 中间 skill 失败 → 不崩溃，对应字段空，其他正常
# ============================================================

def test_wangshuai_failure_does_not_crash():
    """旺衰计算失败，返回完整 dict，旺衰结论为空，日主/四柱正常"""
    with patch("app.skills.divination.wangshuai_skill.calculate_wangshuai",
               side_effect=RuntimeError("测试-旺衰崩溃")):
        result = _call()
    assert set(result.keys()) == _EXPECTED_KEYS, f"key 集合不完整: {set(result.keys()) ^ _EXPECTED_KEYS}"
    assert result["旺衰结论"] == "", "旺衰失败后应置空"
    assert result["旺衰详情"]["总分"] == 0, "旺衰失败后总分应为默认0"
    # 其他字段正常
    assert result["日主"], "日主应正常生成"
    assert result["四柱"], "四柱应正常生成"
    assert result["用神"], "用神应正常生成（来自调候，不受旺衰影响）"
    print("✓ test_wangshuai_failure_does_not_crash")


def test_tiaohou_failure_does_not_crash():
    """调候用神计算失败，返回完整 dict，用神/忌神为空，日主/四柱正常"""
    with patch("app.skills.divination.tiaohou_skill.calculate_tiaohou",
               side_effect=RuntimeError("测试-调候崩溃")):
        result = _call()
    assert set(result.keys()) == _EXPECTED_KEYS
    assert result["用神"] == "", "调候失败后用神应置空"
    assert result["忌神"] == "", "调候失败后忌神应置空"
    assert result["调候描述"] == "", "调候失败后描述应置空"
    # 其他字段正常
    assert result["日主"], "日主应正常生成"
    assert result["四柱"], "四柱应正常生成"
    assert result["旺衰结论"], "旺衰应正常生成（不受调候影响）"
    print("✓ test_tiaohou_failure_does_not_crash")


def test_geju_failure_does_not_crash():
    """格局判定失败，返回完整 dict，格局为空，日主/四柱正常"""
    with patch("app.skills.divination.geju_skill.calculate_geju",
               side_effect=RuntimeError("测试-格局崩溃")):
        result = _call()
    assert set(result.keys()) == _EXPECTED_KEYS
    assert result["格局"] == "", "格局失败后应置空"
    assert result["格局详情"]["类型"] == "", "格局详情类型应置空"
    # 其他字段正常
    assert result["日主"], "日主应正常生成"
    assert result["四柱"], "四柱应正常生成"
    assert result["用神"], "用神应正常生成（不受格局影响）"
    print("✓ test_geju_failure_does_not_crash")


def test_dizhi_relation_failure_does_not_crash():
    """地支关系计算失败，返回完整 dict，地支作用为空"""
    with patch("app.skills.divination.dizhi_relation_skill.analyze_dizhi_relations",
               side_effect=RuntimeError("测试-地支关系崩溃")):
        result = _call()
    assert set(result.keys()) == _EXPECTED_KEYS
    assert result["地支作用"] == "", "地支关系失败后应置空"
    assert result["日主"], "日主应正常生成"
    print("✓ test_dizhi_relation_failure_does_not_crash")


# ============================================================
# 3. 正常路径不回归
# ============================================================

def test_normal_path_still_complete():
    """无 mock 时正常排盘，返回完整 dict 且关键字段非空"""
    result = _call()
    assert set(result.keys()) == _EXPECTED_KEYS
    # 关键字段非空
    for k in ("日主", "四柱", "用神", "忌神", "旺衰结论", "格局", "当前大运", "重点流年"):
        assert result[k], f"正常路径下 {k} 不应为空"
    # 重点流年非空且每项有流月
    assert len(result["重点流年"]) > 0, "重点流年列表不应为空"
    sample = result["重点流年"][0]
    assert "liuyue" in sample, "重点流年项应含 liuyue 字段"
    print("✓ test_normal_path_still_complete")


if __name__ == "__main__":
    test_calculate_bazi_failure_raises_runtimeerror()
    test_wangshuai_failure_does_not_crash()
    test_tiaohou_failure_does_not_crash()
    test_geju_failure_does_not_crash()
    test_dizhi_relation_failure_does_not_crash()
    test_normal_path_still_complete()
    print("\n全部容错测试通过 ✓")
