"""命盘数据使用检查器：检查 LLM 输出是否编造了命盘未提供的数据。

核心逻辑：
1. 从 LLM 输出中提取所有命理相关实体（大运/流年/十神/用神/忌神）
2. 从命盘数据中提取合法实体
3. 比对：LLM 提到的实体必须在命盘数据中存在
"""
import json
import re
from typing import Dict, List, Set


def extract_chart_entities(report: dict) -> Dict[str, Set[str]]:
    """从 LLM 输出中提取所有命理相关实体"""
    entities: Dict[str, Set[str]] = {
        "大运": set(),
        "流年": set(),
        "十神": set(),
        "用神": set(),
        "忌神": set(),
    }
    all_text = json.dumps(report, ensure_ascii=False)

    # 大运干支：匹配"甲寅大运""甲寅运"
    for m in re.finditer(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])[运大]*运", all_text):
        entities["大运"].add(m.group(1))

    # 流年干支：匹配"2034年甲寅"
    for m in re.finditer(r"(\d{4})年([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", all_text):
        entities["流年"].add(f"{m.group(1)}:{m.group(2)}")

    # 十神（黑名单术语）
    shishen_terms = ["七杀", "正官", "偏印", "正印", "伤官", "食神", "比肩", "劫财", "偏财", "正财"]
    for term in shishen_terms:
        if term in all_text:
            entities["十神"].add(term)

    # 用神/忌神：匹配"用神X""忌神X"（X 为五行：金木水火土）
    for m in re.finditer(r"用神[是为]?([\u4e00-\u9fa5])", all_text):
        val = m.group(1)
        # 只保留五行值，过滤"年""月"等非五行字符
        if val in "金木水火土":
            entities["用神"].add(val)
    for m in re.finditer(r"忌神[是为]?([\u4e00-\u9fa5])", all_text):
        val = m.group(1)
        if val in "金木水火土":
            entities["忌神"].add(val)

    return entities


def extract_chart_data_entities(chart_data: dict) -> Dict[str, Set[str]]:
    """从命盘数据中提取所有合法实体"""
    entities: Dict[str, Set[str]] = {
        "大运": set(),
        "流年": set(),
        "十神": set(),
        "用神": set(),
        "忌神": set(),
    }

    # 大运：从"当前大运"、"大运列表"提取
    # 注意：未起运的命盘"当前大运"为空，合法大运以"大运列表"为准
    current_dayun = chart_data.get("当前大运", "")
    for m in re.finditer(r"([甲乙丙丁戊己庚辛壬][子丑寅卯辰巳午未申酉戌亥])", str(current_dayun)):
        entities["大运"].add(m.group(1))
    for dy in chart_data.get("大运列表", []) or []:
        if isinstance(dy, dict):
            gz_m = re.search(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", str(dy.get("ganzhi", "")))
            if gz_m:
                entities["大运"].add(gz_m.group(1))
        else:
            for m in re.finditer(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", str(dy)):
                entities["大运"].add(m.group(1))

    # 流年：从"重点流年"提取
    # item 为 dict（{"year": 2032, "ganzhi": "壬子", ...}）时直接读字段；
    # item 为字符串（"2032年壬子"）时用正则解析，两处均需匹配到年份+干支才算合法实体
    key_liunian = chart_data.get("重点流年", [])
    if isinstance(key_liunian, list):
        for item in key_liunian:
            if isinstance(item, dict):
                year = item.get("year")
                gz_m = re.search(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", str(item.get("ganzhi", "")))
                if year and gz_m:
                    entities["流年"].add(f"{int(year)}:{gz_m.group(1)}")
            else:
                text = str(item)
                year_m = re.search(r"(\d{4})年?", text)
                gz_m = re.search(r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])", text)
                if year_m and gz_m:
                    entities["流年"].add(f"{year_m.group(1)}:{gz_m.group(1)}")

    # 用神/忌神
    yongshen = chart_data.get("用神", "")
    if yongshen:
        for m in re.finditer(r"([\u4e00-\u9fa5])", str(yongshen)):
            entities["用神"].add(m.group(1))
    jishen = chart_data.get("忌神", "")
    if jishen:
        for m in re.finditer(r"([\u4e00-\u9fa5])", str(jishen)):
            entities["忌神"].add(m.group(1))

    return entities


def check_chart_usage(report: dict, chart_data: dict) -> List[Dict]:
    """检查 LLM 输出是否编造了命盘未提供的数据。

    Args:
        report: 追问报告 JSON
        chart_data: 命盘数据 dict（generate_full_analysis 返回的中文字段 dict）

    Returns:
        违规列表
    """
    violations = []
    report_entities = extract_chart_entities(report)
    chart_entities = extract_chart_data_entities(chart_data)

    # 1. 大运：LLM 提到的大运干支必须在命盘大运列表中
    for dy in report_entities["大运"]:
        if dy not in chart_entities["大运"]:
            violations.append({
                "type": "编造大运",
                "entity": dy,
                "detail": f"LLM 提到大运'{dy}'，但命盘中未找到",
                "命盘已有": list(chart_entities["大运"]),
                "location": "report_text",
                "expected": f"LLM只能引用命盘中的大运：{list(chart_entities['大运'])}",
                "reason": "编造不存在的大运会误导用户，属于严重的事实错误",
            })

    # 2. 流年：LLM 提到的流年干支必须在重点流年列表中
    chart_years = {ln.split(":")[0] for ln in chart_entities["流年"]}
    for ln in report_entities["流年"]:
        year, gz = ln.split(":")
        if ln not in chart_entities["流年"]:
            if year in chart_years:
                violations.append({
                    "type": "流年干支不一致",
                    "entity": ln,
                    "detail": f"LLM 说{year}年是{gz}，但命盘数据不一致",
                    "命盘已有": list(chart_entities["流年"]),
                    "location": "report_text",
                    "expected": f"{year}年的干支应与命盘一致（命盘记录：{list(chart_entities['流年'])}）",
                    "reason": "流年干支错误会导致后续吉凶判断全部错误，属于致命性事实错误",
                })
            else:
                violations.append({
                    "type": "编造流年",
                    "entity": ln,
                    "detail": f"LLM 提到{year}年{gz}，但命盘重点流年未包含该年",
                    "命盘已有": list(chart_entities["流年"]),
                    "location": "report_text",
                    "expected": f"LLM只能引用命盘中的重点流年：{list(chart_entities['流年'])}",
                    "reason": "编造不存在的流年会误导用户决策，属于严重的事实错误",
                })

    # 3. 用神/忌神：与命盘一致
    for ys in report_entities["用神"]:
        if ys not in chart_entities["用神"]:
            violations.append({
                "type": "用神不一致",
                "entity": ys,
                "detail": f"LLM 说用神是'{ys}'，命盘用神是'{chart_data.get('用神', '')}'",
                "location": "report_text",
                "expected": f"用神应与命盘一致（命盘用神：'{chart_data.get('用神', '')}'）",
                "reason": "用神/忌神是命理分析的核心依据，与命盘不一致会导致整个分析方向错误",
            })

    for js in report_entities["忌神"]:
        if js not in chart_entities["忌神"]:
            violations.append({
                "type": "忌神不一致",
                "entity": js,
                "detail": f"LLM 说忌神是'{js}'，命盘忌神是'{chart_data.get('忌神', '')}'",
                "location": "report_text",
                "expected": f"忌神应与命盘一致（命盘忌神：'{chart_data.get('忌神', '')}'）",
                "reason": "用神/忌神是命理分析的核心依据，与命盘不一致会导致整个分析方向错误",
            })

    return violations
