"""排盘正确性检查器：比对排盘结果与标准答案，检测排盘算法 bug。

检查项：
1. 四柱干支
2. 日主天干
3. 十神（年干/月干/时干/各支支神）
4. 大运方向（顺/逆）
5. 起运年龄
6. 大运列表（含详细信息：天干五行、地支五行、用神标记、综合判断）
7. 流年干支（含详细信息：天干五行、地支五行、用神标记、流年判断）
8. 流月详细信息（含吉凶判断）
"""
from typing import Dict, List


# 字段映射表：支持中英文 key 互转
FIELD_MAPPING = {
    "干支": "ganzhi",
    "起始年龄": "start_age",
    "起始年份": "start_year",
    "天干": "tiangan",
    "地支": "dizhi",
    "天干五行": "tian_wuxing",
    "地支五行": "di_wuxing",
    "大运五行": "dayun_wuxing",
    "流年五行": "liunian_wuxing",
    "流月五行": "liuyue_wuxing",
    "用神标记": "is_yongshen",
    "忌神标记": "is_jishen",
    "与命局交互": "interactions",
    "与大运交互": "dayun_interactions",
    "综合判断": "overall_judge",
    "综合描述": "description",
    "流年判断": "judge",
    "判断理由": "reason",
    "重点提示": "suggestion",
    "吉凶": "judge",
    "理由": "reason",
}


def normalize_chart_data(data: dict, use_chinese: bool = True) -> dict:
    """统一数据格式，支持中英文 key 互转。
    
    Args:
        data: 原始数据 dict
        use_chinese: True 表示将英文 key 转为中文，False 表示将中文 key 转为英文
    
    Returns:
        统一格式后的 dict
    """
    if use_chinese:
        # 英文 -> 中文
        reverse_mapping = {v: k for k, v in FIELD_MAPPING.items()}
        return {reverse_mapping.get(k, k): v for k, v in data.items()}
    else:
        # 中文 -> 英文
        return {FIELD_MAPPING.get(k, k): v for k, v in data.items()}


def check_chart_correctness(generated: dict, expected: dict) -> List[Dict]:
    """比对排盘结果与标准答案。

    Args:
        generated: 排盘系统生成的命盘数据 dict
        expected: 标准答案 dict（来自 eval_chart_dataset.json）

    Returns:
        违规列表
    """
    violations = []

    # 1. 四柱干支（去空格比对）
    gen_pillars = generated.get("四柱", "").replace(" ", "")
    exp_pillars = expected.get("四柱", "").replace(" ", "")
    if gen_pillars != exp_pillars:
        violations.append({
            "type": "四柱错误",
            "expected": exp_pillars,
            "actual": gen_pillars,
            "location": "四柱",
        })

    # 2. 日主天干
    gen_rizhu = generated.get("日主", "")
    exp_rizhu = expected.get("日主天干", "")
    # 日主格式可能是"己土"或"己"，取第一个字符比对
    gen_rizhu_char = gen_rizhu[0] if gen_rizhu else ""
    if gen_rizhu_char != exp_rizhu:
        violations.append({
            "type": "日主天干错误",
            "expected": exp_rizhu,
            "actual": gen_rizhu_char,
            "location": "日主",
        })

    # 3. 十神比对
    gen_shishen = generated.get("十神分布", {})
    exp_shishen = expected.get("十神", {})
    if isinstance(gen_shishen, dict) and isinstance(exp_shishen, dict):
        # 天干十神
        for key in ["年干", "月干", "时干"]:
            exp_val = exp_shishen.get(key, "")
            gen_val = gen_shishen.get(key, "")
            if exp_val and gen_val != exp_val:
                violations.append({
                    "type": "十神错误",
                    "position": key,
                    "expected": exp_val,
                    "actual": gen_val,
                    "location": f"十神分布.{key}",
                })

        # 地支十神（支神）
        for key in ["年支", "月支", "日支", "时支"]:
            exp_val = exp_shishen.get(key, [])
            gen_val = gen_shishen.get(key, [])
            if isinstance(exp_val, list) and isinstance(gen_val, list):
                exp_set = set(exp_val)
                gen_set = set(gen_val)
                if exp_set != gen_set:
                    violations.append({
                        "type": "支神错误",
                        "position": key,
                        "expected": sorted(exp_set),
                        "actual": sorted(gen_set),
                        "location": f"十神分布.{key}",
                    })

    # 4. 大运方向
    gen_dir = generated.get("大运方向", "")
    exp_dir = expected.get("大运方向", "")
    if exp_dir and gen_dir != exp_dir:
        violations.append({
            "type": "大运方向错误",
            "expected": exp_dir,
            "actual": gen_dir,
            "location": "大运方向",
        })

    # 5. 起运年龄
    gen_start = generated.get("起运年龄", "")
    exp_start = expected.get("起运年龄", "")
    if exp_start is not None:
        try:
            gen_start_float = float(gen_start) if gen_start else 0
            exp_start_float = float(exp_start)
            if abs(gen_start_float - exp_start_float) > 0.5:
                violations.append({
                    "type": "起运年龄错误",
                    "expected": exp_start_float,
                    "actual": gen_start_float,
                    "location": "起运年龄",
                })
        except (ValueError, TypeError):
            pass

    # 6. 大运列表（含详细信息）
    gen_dayun_list = generated.get("大运列表", [])
    exp_dayun_list = expected.get("大运列表", [])
    if isinstance(gen_dayun_list, list) and isinstance(exp_dayun_list, list):
        # 比对前几个大运
        for i, exp_dy in enumerate(exp_dayun_list[:5]):
            if i < len(gen_dayun_list):
                gen_dy = gen_dayun_list[i]
                if isinstance(gen_dy, dict):
                    # 比对干支
                    gen_gz = gen_dy.get("ganzhi", "") or gen_dy.get("干支", "")
                    exp_gz = exp_dy.get("干支", "") if isinstance(exp_dy, dict) else exp_dy
                    if gen_gz != exp_gz:
                        violations.append({
                            "type": "大运列表错误",
                            "position": i,
                            "expected": exp_gz,
                            "actual": gen_gz,
                            "location": f"大运列表[{i}]",
                        })
                    
                    # 比对天干五行（如果标准数据有此字段）
                    if isinstance(exp_dy, dict) and exp_dy.get("天干五行"):
                        gen_tian_wx = gen_dy.get("天干五行", "") or gen_dy.get("tian_wuxing", "")
                        exp_tian_wx = exp_dy.get("天干五行", "")
                        if gen_tian_wx and gen_tian_wx != exp_tian_wx:
                            violations.append({
                                "type": "大运天干五行错误",
                                "position": i,
                                "expected": exp_tian_wx,
                                "actual": gen_tian_wx,
                                "location": f"大运列表[{i}].天干五行",
                            })
                    
                    # 比对地支五行（如果标准数据有此字段）
                    if isinstance(exp_dy, dict) and exp_dy.get("地支五行"):
                        gen_di_wx = gen_dy.get("地支五行", "") or gen_dy.get("di_wuxing", "")
                        exp_di_wx = exp_dy.get("地支五行", "")
                        if gen_di_wx and gen_di_wx != exp_di_wx:
                            violations.append({
                                "type": "大运地支五行错误",
                                "position": i,
                                "expected": exp_di_wx,
                                "actual": gen_di_wx,
                                "location": f"大运列表[{i}].地支五行",
                            })
                    
                    # 比对综合判断（如果标准数据有此字段）
                    if isinstance(exp_dy, dict) and exp_dy.get("综合判断"):
                        gen_judge = gen_dy.get("综合判断", "") or gen_dy.get("overall_judge", "")
                        exp_judge = exp_dy.get("综合判断", "")
                        if gen_judge and gen_judge != exp_judge:
                            violations.append({
                                "type": "大运综合判断错误",
                                "position": i,
                                "expected": exp_judge,
                                "actual": gen_judge,
                                "location": f"大运列表[{i}].综合判断",
                            })

    # 7. 流年干支（含详细信息）
    gen_liunian = generated.get("重点流年", [])
    exp_liunian = expected.get("流年", {})
    if isinstance(gen_liunian, list) and isinstance(exp_liunian, dict):
        for year_str, exp_ln_data in exp_liunian.items():
            try:
                year = int(year_str)
            except ValueError:
                continue
            
            # exp_ln_data 可能是字符串（干支）或字典（详细信息）
            exp_gz = exp_ln_data.get("干支", "") if isinstance(exp_ln_data, dict) else exp_ln_data
            
            # 在 gen_liunian 中查找该年
            found = False
            for item in gen_liunian:
                if isinstance(item, dict):
                    item_year = item.get("year", "")
                    item_gz = item.get("ganzhi", "") or item.get("干支", "")
                    try:
                        if int(item_year) == year:
                            # 比对干支
                            if item_gz != exp_gz:
                                violations.append({
                                    "type": "流年干支错误",
                                    "year": year,
                                    "expected": exp_gz,
                                    "actual": item_gz,
                                    "location": f"重点流年.{year}",
                                })
                            
                            # 比对天干五行（如果标准数据有此字段）
                            if isinstance(exp_ln_data, dict) and exp_ln_data.get("天干五行"):
                                gen_tian_wx = item.get("天干五行", "") or item.get("tian_wuxing", "")
                                exp_tian_wx = exp_ln_data.get("天干五行", "")
                                if gen_tian_wx and gen_tian_wx != exp_tian_wx:
                                    violations.append({
                                        "type": "流年天干五行错误",
                                        "year": year,
                                        "expected": exp_tian_wx,
                                        "actual": gen_tian_wx,
                                        "location": f"流年.{year}.天干五行",
                                    })
                            
                            # 比对地支五行（如果标准数据有此字段）
                            if isinstance(exp_ln_data, dict) and exp_ln_data.get("地支五行"):
                                gen_di_wx = item.get("地支五行", "") or item.get("di_wuxing", "")
                                exp_di_wx = exp_ln_data.get("地支五行", "")
                                if gen_di_wx and gen_di_wx != exp_di_wx:
                                    violations.append({
                                        "type": "流年地支五行错误",
                                        "year": year,
                                        "expected": exp_di_wx,
                                        "actual": gen_di_wx,
                                        "location": f"流年.{year}.地支五行",
                                    })
                            
                            # 比对流年判断（如果标准数据有此字段）
                            if isinstance(exp_ln_data, dict) and exp_ln_data.get("流年判断"):
                                gen_judge = item.get("流年判断", "") or item.get("judge", "")
                                exp_judge = exp_ln_data.get("流年判断", "")
                                if gen_judge and gen_judge != exp_judge:
                                    violations.append({
                                        "type": "流年判断错误",
                                        "year": year,
                                        "expected": exp_judge,
                                        "actual": gen_judge,
                                        "location": f"流年.{year}.流年判断",
                                    })
                            
                            found = True
                            break
                    except (ValueError, TypeError):
                        pass
            if not found:
                violations.append({
                    "type": "流年缺失",
                    "year": year,
                    "expected": exp_gz,
                    "location": f"重点流年.{year}",
                })
    
    # 8. 流月详细信息（如果标准数据有此字段）
    gen_liuyue = generated.get("流月数据", {}) or generated.get("流月", {})
    exp_liuyue = expected.get("流月_2026", {})
    if isinstance(gen_liuyue, dict) and isinstance(exp_liuyue, dict):
        for month_key, exp_ly_data in exp_liuyue.items():
            if not isinstance(exp_ly_data, dict):
                continue
            
            gen_ly = gen_liuyue.get(month_key, {})
            if not isinstance(gen_ly, dict):
                continue
            
            # 比对干支
            gen_gz = gen_ly.get("干支", "") or gen_ly.get("ganzhi", "")
            exp_gz = exp_ly_data.get("干支", "")
            if gen_gz and exp_gz and gen_gz != exp_gz:
                violations.append({
                    "type": "流月干支错误",
                    "month": month_key,
                    "expected": exp_gz,
                    "actual": gen_gz,
                    "location": f"流月.{month_key}",
                })
            
            # 比对吉凶判断（如果标准数据有此字段）
            if exp_ly_data.get("吉凶"):
                gen_judge = gen_ly.get("吉凶", "") or gen_ly.get("judge", "")
                exp_judge = exp_ly_data.get("吉凶", "")
                if gen_judge and gen_judge != exp_judge:
                    violations.append({
                        "type": "流月吉凶错误",
                        "month": month_key,
                        "expected": exp_judge,
                        "actual": gen_judge,
                        "location": f"流月.{month_key}.吉凶",
                    })

    return violations
