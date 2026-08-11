"""命盘数据完整性校验 + 指纹审计。

在代码层面（不依赖 prompt）保证首次报告和追问报告生成时命盘数据正确输入：
- validate_chart_data：校验 8 个关键字段非空，返回 (是否通过, 缺失字段列表)
- get_chart_fingerprint：提取命盘关键摘要，用于 LLM 输出后日志审计

校验失败时由调用方决定处理方式（当前约定：记录告警 + 降级生成）。
"""
from typing import Any, Dict, List, Tuple

# 命盘必需字段（基于 _build_context_vars 实际使用的字段推导）
# (中文key, 字段类型, 用途说明)
_CHART_REQUIRED_FIELDS = [
    ("日主", "str", "日主天干描述"),
    ("四柱", "str", "四柱干支"),
    ("用神", "str", "调候用神"),
    ("忌神", "str", "忌神五行"),
    ("旺衰结论", "str", "日主旺衰"),
    ("格局", "str", "命局格局"),
    ("当前大运", "str", "当前大运干支"),
    ("重点流年", "list", "重点流年吉凶"),
]

# 缺失字段在 prompt 里的统一标注（让 LLM 知道该字段无数据、不要编造）
MISSING_MARKER = "（命盘数据缺失）"


def validate_chart_data(analysis_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """校验命盘数据完整性。

    Args:
        analysis_data: generate_full_analysis 返回的中文 key dict

    Returns:
        (是否通过, 缺失字段中文key列表)
    """
    if not analysis_data or not isinstance(analysis_data, dict):
        return False, ["整个命盘数据为空"]

    missing = []
    for key, ftype, _desc in _CHART_REQUIRED_FIELDS:
        val = analysis_data.get(key)
        if val is None:
            missing.append(key)
        elif ftype == "str" and (not isinstance(val, str) or not val.strip()):
            missing.append(key)
        elif ftype == "list" and (not isinstance(val, (list, tuple)) or len(val) == 0):
            missing.append(key)
    return (len(missing) == 0), missing


def get_chart_fingerprint(analysis_data: Dict[str, Any]) -> Dict[str, str]:
    """提取命盘指纹（关键字段摘要），用于 LLM 输出后日志审计。

    记录命盘关键数据 + LLM 输出摘要到日志，便于事后人工核对
    LLM 输出是否与命盘一致（不做强制拦截，避免误杀叙事化大白话转述）。
    """
    if not analysis_data or not isinstance(analysis_data, dict):
        return {"错误": "命盘数据为空"}
    return {
        "日主": str(analysis_data.get("日主", ""))[:30],
        "用神": str(analysis_data.get("用神", ""))[:10],
        "忌神": str(analysis_data.get("忌神", ""))[:10],
        "当前大运": str(analysis_data.get("当前大运", ""))[:20],
        "重点流年": str(analysis_data.get("重点流年", ""))[:100],
    }
