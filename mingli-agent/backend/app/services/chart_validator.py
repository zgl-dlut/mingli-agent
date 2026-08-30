"""命盘数据完整性校验 + 指纹审计。

在代码层面（不依赖 prompt）保证首次报告和追问报告生成时命盘数据正确输入：
- validate_chart_data：校验 8 个关键字段非空，返回 (是否通过, 缺失字段列表)
- validate_chart_data_with_values：校验字段值的正确性（格式、范围）
- get_chart_fingerprint：提取命盘关键摘要，用于 LLM 输出后日志审计

校验失败时由调用方决定处理方式（当前约定：记录告警 + 降级生成）。
"""
import re
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


# 天干地支常量
TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
WUXING = ["金", "木", "水", "火", "土"]

# 六十甲子（用于校验干支格式）
LIUSHI_JIAZI = []
for i in range(60):
    gan = TIANGAN[i % 10]
    zhi = DIZHI[i % 12]
    LIUSHI_JIAZI.append(gan + zhi)


def validate_chart_data_with_values(analysis_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """校验命盘数据值的正确性（格式、范围）。

    在 validate_chart_data 基础上，进一步校验字段值的格式和取值范围：
    - 四柱格式：必须是"XX XX XX XX"格式，每个XX是天干地支组合
    - 日主格式：必须是"X水/火/木/金/土"格式，X是天干
    - 用神/忌神：必须是五行之一（金/木/水/火/土）
    - 当前大运：干支必须符合六十甲子
    - 重点流年：每个流年的干支必须符合六十甲子

    Args:
        analysis_data: generate_full_analysis 返回的中文 key dict

    Returns:
        (是否通过, 错误信息列表)
    """
    if not analysis_data or not isinstance(analysis_data, dict):
        return False, ["命盘数据为空"]

    errors = []

    # 1. 校验四柱格式
    sizhu = analysis_data.get("四柱", "")
    if sizhu:
        # 四柱格式应该是"甲子 乙丑 丙寅 丁卯"
        sizhu_pattern = r'^([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])\s+([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])\s+([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])\s+([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])$'
        if not re.match(sizhu_pattern, sizhu):
            errors.append(f"四柱格式错误: '{sizhu}'，应为'甲子 乙丑 丙寅 丁卯'格式")
        else:
            # 进一步校验每个干支是否在六十甲子中
            parts = sizhu.split()
            for part in parts:
                if part not in LIUSHI_JIAZI:
                    errors.append(f"四柱干支不在六十甲子中: '{part}'")

    # 2. 校验日主格式
    day_master = analysis_data.get("日主", "")
    if day_master:
        # 日主格式可能是"甲木"、"甲"、"甲木（阳木参天）"等
        # 先提取前两个字符（天干+五行）
        day_master_short = day_master[:2] if len(day_master) >= 2 else day_master
        day_master_pattern = r'^([甲乙丙丁戊己庚辛壬癸])([木火土金水])?$'
        match = re.match(day_master_pattern, day_master_short)
        if not match:
            errors.append(f"日主格式错误: '{day_master}'，应为'甲木'或'甲'格式")
        else:
            # 如果包含五行，校验五行是否正确
            if match.group(2):
                tiangan = match.group(1)
                wuxing = match.group(2)
                # 天干对应五行：甲乙-木，丙丁-火，戊己-土，庚辛-金，壬癸-水
                tiangan_wuxing_map = {
                    "甲": "木", "乙": "木",
                    "丙": "火", "丁": "火",
                    "戊": "土", "己": "土",
                    "庚": "金", "辛": "金",
                    "壬": "水", "癸": "水",
                }
                expected_wuxing = tiangan_wuxing_map.get(tiangan)
                if expected_wuxing and wuxing != expected_wuxing:
                    errors.append(f"日主五行不匹配: '{day_master}'，{tiangan}应为{expected_wuxing}")

    # 3. 校验用神/忌神
    for field in ["用神", "忌神"]:
        value = analysis_data.get(field, "")
        if value:
            # 用神/忌神可能是单个五行，也可能是多个（如"金水"）
            # 提取所有五行字符
            wuxing_chars = re.findall(r'[金木水火土]', value)
            if not wuxing_chars:
                errors.append(f"{field}未包含有效五行: '{value}'")
            else:
                for char in wuxing_chars:
                    if char not in WUXING:
                        errors.append(f"{field}包含无效五行: '{char}'")

    # 4. 校验当前大运干支
    current_dayun = analysis_data.get("当前大运", "")
    if current_dayun:
        # 当前大运格式可能是"甲子"或"甲子 2020-2029"
        dayun_ganzhi = current_dayun.split()[0] if " " in current_dayun else current_dayun
        if dayun_ganzhi not in LIUSHI_JIAZI:
            errors.append(f"当前大运干支不在六十甲子中: '{dayun_ganzhi}'")

    # 5. 校验重点流年干支
    key_liunian = analysis_data.get("重点流年", [])
    if isinstance(key_liunian, list):
        for liunian in key_liunian:
            if isinstance(liunian, dict):
                ganzhi = liunian.get("干支", "")
                if ganzhi and ganzhi not in LIUSHI_JIAZI:
                    errors.append(f"重点流年干支不在六十甲子中: '{ganzhi}'")

    return (len(errors) == 0), errors
