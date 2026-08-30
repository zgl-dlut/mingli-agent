"""
端到端集成测试：从排盘到报告生成

验证整个链路的正确性：
1. 排盘算法生成 analysis_data
2. 数据传递校验通过
3. 构建 prompt
4. 模拟 LLM 生成报告
5. 验证报告中的干支、五行与排盘数据一致
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.skills.orchestrator import generate_full_analysis
from app.services.chart_validator import validate_chart_data_with_values
from app.services.followup_structured import (
    _detect_liuyue_ganzhi_mismatch,
    _detect_dayun_ganzhi_mismatch,
    _detect_liunian_ganzhi_mismatch,
    _detect_yongshen_wuxing_mismatch,
    _detect_missing_tool_calls,
)


# ============================================================
# 测试用例：标准生辰信息
# ============================================================

E2E_TEST_CASES = [
    {
        "name": "1994-10-13 18:03 男 长春",
        "birth_date": "1994-10-13",
        "birth_time": "18:03",
        "longitude": 125.32,
        "latitude": 43.88,
        "gender": "男",
        "location": "吉林省长春市",
        "question": "27年会离开当前公司吗？",
    },
    {
        "name": "1990-11-10 08:00 女 晋中",
        "birth_date": "1990-11-10",
        "birth_time": "08:00",
        "longitude": 112.75,
        "latitude": 37.69,
        "gender": "女",
        "location": "山西省晋中市",
        "question": "27年几月适合离职？",
    },
]


# ============================================================
# 测试函数
# ============================================================

@pytest.mark.parametrize("case", E2E_TEST_CASES, ids=[c["name"] for c in E2E_TEST_CASES])
def test_e2e_data_validation(case):
    """端到端测试：数据传递校验"""
    # 1. 排盘
    bazi_data = generate_full_analysis(
        birth_date=case["birth_date"],
        birth_time=case["birth_time"],
        longitude=case["longitude"],
        latitude=case["latitude"],
        gender=case["gender"],
        location=case["location"],
    )
    
    # 2. 数据传递校验
    is_valid, errors = validate_chart_data_with_values(bazi_data)
    
    assert is_valid, f"[{case['name']}] 数据传递校验失败: {errors}"


@pytest.mark.parametrize("case", E2E_TEST_CASES, ids=[c["name"] for c in E2E_TEST_CASES])
def test_e2e_detection_functions(case):
    """端到端测试：检测函数验证"""
    # 1. 排盘
    bazi_data = generate_full_analysis(
        birth_date=case["birth_date"],
        birth_time=case["birth_time"],
        longitude=case["longitude"],
        latitude=case["latitude"],
        gender=case["gender"],
        location=case["location"],
    )
    
    # 2. 构造一个"完美"的报告（与排盘数据完全一致）
    perfect_report = {
        "opening": {
            "verdict": f"根据命盘分析，{bazi_data.get('当前大运', '')}大运期间，{bazi_data.get('用神', '')}是用神。"
        },
        "subtopics": [
            {
                "title": "核心问题",
                "blocks": [
                    {
                        "keyword": "大运影响",
                        "narrative": f"你现在走的{bazi_data.get('当前大运', '').split()[0]}大运，对你有利。"
                    }
                ]
            }
        ],
        "summary": {
            "items": [
                {
                    "keyword": "建议",
                    "text": f"把握{bazi_data.get('用神', '')}旺的时机。"
                }
            ]
        }
    }
    
    # 3. 验证检测函数不会误报
    violations = []
    violations += _detect_dayun_ganzhi_mismatch(perfect_report, bazi_data)
    violations += _detect_liunian_ganzhi_mismatch(perfect_report, bazi_data)
    violations += _detect_yongshen_wuxing_mismatch(perfect_report, bazi_data)
    
    assert len(violations) == 0, f"[{case['name']}] 完美报告被误报: {violations}"


def test_e2e_detection_with_wrong_data():
    """端到端测试：检测函数能识别错误数据"""
    # 1. 排盘
    bazi_data = generate_full_analysis(
        birth_date="1994-10-13",
        birth_time="18:03",
        longitude=125.32,
        latitude=43.88,
        gender="男",
        location="吉林省长春市",
    )
    
    # 2. 构造一个"错误"的报告（大运干支错误）
    wrong_report = {
        "opening": {
            "verdict": "根据命盘分析，壬午大运期间，火是用神。"
        },
        "subtopics": [
            {
                "title": "核心问题",
                "blocks": [
                    {
                        "keyword": "大运影响",
                        "narrative": "你现在走的壬午大运，对你有利。"
                    }
                ]
            }
        ],
        "summary": {
            "items": []
        }
    }
    
    # 3. 验证检测函数能识别错误
    violations = _detect_dayun_ganzhi_mismatch(wrong_report, bazi_data)
    
    assert len(violations) > 0, "错误报告应该被检测到"
    assert "大运干支错误" in violations[0], f"应该检测到大运干支错误，实际: {violations[0]}"


def test_e2e_missing_tool_call_detection():
    """端到端测试：检测缺少工具调用"""
    # 1. 构造一个提到流月干支但没有调用工具的报告
    report_without_tool_call = {
        "opening": {
            "verdict": "根据命盘分析，9月（丁酉月）适合行动。"
        },
        "subtopics": [
            {
                "title": "月份建议",
                "blocks": [
                    {
                        "keyword": "最佳时机",
                        "narrative": "9月（丁酉月）是最佳时机。"
                    }
                ]
            }
        ],
        "summary": {
            "items": []
        }
    }
    
    # 2. 验证检测函数能识别缺少工具调用
    violations = _detect_missing_tool_calls(report_without_tool_call, [])
    
    assert len(violations) > 0, "应该检测到缺少工具调用"
    assert "未调用 get_liuyue_detail 工具" in violations[0], f"应该检测到工具调用缺失，实际: {violations[0]}"


def test_e2e_tool_call_present():
    """端到端测试：工具调用存在时不报错"""
    # 1. 构造一个提到流月干支且调用了工具的报告
    report_with_tool_call = {
        "opening": {
            "verdict": "根据命盘分析，9月（丁酉月）适合行动。"
        },
        "subtopics": [
            {
                "title": "月份建议",
                "blocks": [
                    {
                        "keyword": "最佳时机",
                        "narrative": "9月（丁酉月）是最佳时机。"
                    }
                ]
            }
        ],
        "summary": {
            "items": []
        }
    }
    
    # 2. 模拟工具调用记录
    tool_calls = [
        {
            "function": {
                "name": "get_liuyue_detail",
                "arguments": '{"year": 2027}'
            }
        }
    ]
    
    # 3. 验证检测函数不会误报
    violations = _detect_missing_tool_calls(report_with_tool_call, tool_calls)
    
    assert len(violations) == 0, f"工具调用存在时不应该报错，实际: {violations}"


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("端到端集成测试")
    print("=" * 80)
    
    for case in E2E_TEST_CASES:
        print(f"\n【{case['name']}】")
        
        # 1. 排盘
        bazi_data = generate_full_analysis(
            birth_date=case["birth_date"],
            birth_time=case["birth_time"],
            longitude=case["longitude"],
            latitude=case["latitude"],
            gender=case["gender"],
            location=case["location"],
        )
        
        # 2. 数据传递校验
        is_valid, errors = validate_chart_data_with_values(bazi_data)
        status = "✓" if is_valid else "✗"
        print(f"  {status} 数据传递校验: {'通过' if is_valid else f'失败 - {errors}'}")
        
        # 3. 关键字段
        print(f"  四柱: {bazi_data.get('四柱', '')}")
        print(f"  日主: {bazi_data.get('日主', '')}")
        print(f"  用神: {bazi_data.get('用神', '')}")
        print(f"  忌神: {bazi_data.get('忌神', '')}")
        print(f"  当前大运: {bazi_data.get('当前大运', '')}")
    
    print("\n" + "=" * 80)
