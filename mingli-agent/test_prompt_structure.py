#!/usr/bin/env python3
"""
命理解读API结构测试脚本

测试目标：
1. 覆盖个人事业、财务、爱情、健康等问题
2. 覆盖家人、子女、爱人等关系类问题
3. 检查返回结构中是否有问题拆解
4. 检查格式结构是否正常（标题、关键词、段落等）
5. 评估正确率和稳定性

测试方法：
1. 使用固定八字数据进行测试，排除排盘差异
2. 对每个问题类别发送请求，收集返回内容
3. 分析返回结构是否符合规范
"""

import json
import time
import asyncio
import aiohttp
import re
from typing import List, Dict, Any

# 测试配置
BASE_URL = "http://localhost:8000"
TIMEOUT = 120

# 测试用八字数据（提前获取，避免每次重新排盘）
TEST_BAZI_DATA = {
    "四柱": "己卯 甲子 癸未 壬子",
    "日主": "癸水（阴水雨露）",
    "月令": "子月（仲冬）",
    "旺衰": "偏旺",
    "旺衰结论": "癸水生于子月得令，又有日支未土、时支子水帮身，虽年干己土七杀透出，但水势太旺，综合判断为偏旺。",
    "格局": "七杀格",
    "格局解释": "年干己土七杀透出，月干甲木伤官，构成伤官制杀格局。",
    "用神": "火土",
    "忌神": "金水",
    "调候": "丙火",
    "调候解释": "子月水寒，急需丙火暖局，调候为急。",
    "十神分布": "七杀:2, 伤官:2, 正财:1, 劫财:2, 比肩:2",
    "五行分布": "木:3, 火:1, 土:2, 金:0, 水:4",
    "地支作用": "子卯相刑，子未相害，子子自刑",
    "调候描述": "寒水无火，金水冷寒，格局偏枯。",
    "大运": [
        {"year": "2004", "ganzhi": "乙丑", "desc": "伤官生财"},
        {"year": "2014", "ganzhi": "丙寅", "desc": "食神坐杀"},
        {"year": "2024", "ganzhi": "丁卯", "desc": "伤官生财"},
        {"year": "2034", "ganzhi": "戊辰", "desc": "正官合身"},
        {"year": "2044", "ganzhi": "己巳", "desc": "七杀坐财"},
    ],
    "流年": [
        {"year": "2024", "ganzhi": "甲辰", "desc": "伤官见官"},
        {"year": "2025", "ganzhi": "乙巳", "desc": "食神坐财"},
        {"year": "2026", "ganzhi": "丙午", "desc": "正财坐杀"},
        {"year": "2027", "ganzhi": "丁未", "desc": "七杀坐库"},
        {"year": "2028", "ganzhi": "戊申", "desc": "正官坐劫"},
    ],
    "命格箴言": "寒水得暖，否极泰来",
    "命格箴言标签": {
        "调候标签": "寒水调候",
        "十神做功标签": "伤官制杀"
    },
    "年龄": 26,
    "年龄阶段": "青年期"
}

# 测试用例定义
TEST_CASES = [
    {
        "category": "事业",
        "question": "我今年适合跳槽吗？跳槽后能拿到更高的薪资吗？",
        "expected_keywords": ["跳槽", "薪资", "事业", "工作"],
        "expected_structure": ["问题拆解", "核心结论", "行动建议"]
    },
    {
        "category": "事业",
        "question": "我应该选择安稳的国企还是有挑战性的创业公司？",
        "expected_keywords": ["国企", "创业", "事业选择", "职业规划"],
        "expected_structure": ["问题拆解", "核心结论", "对比分析"]
    },
    {
        "category": "财务",
        "question": "今年我的财运怎么样？适合投资股票吗？",
        "expected_keywords": ["财运", "投资", "股票", "收入"],
        "expected_structure": ["问题拆解", "核心结论", "理财建议"]
    },
    {
        "category": "财务",
        "question": "我什么时候能买房？需要注意什么？",
        "expected_keywords": ["买房", "房产", "财务规划", "投资"],
        "expected_structure": ["问题拆解", "核心结论", "时机分析"]
    },
    {
        "category": "爱情",
        "question": "我今年能找到对象吗？我的另一半是什么样的人？",
        "expected_keywords": ["对象", "另一半", "感情", "婚姻"],
        "expected_structure": ["问题拆解", "核心结论", "伴侣特征"]
    },
    {
        "category": "爱情",
        "question": "我和现任伴侣的关系会有结果吗？",
        "expected_keywords": ["伴侣", "关系", "婚姻", "感情"],
        "expected_structure": ["问题拆解", "核心结论", "关系分析"]
    },
    {
        "category": "健康",
        "question": "我今年需要注意哪些健康问题？身体状况怎么样？",
        "expected_keywords": ["健康", "身体", "疾病", "养生"],
        "expected_structure": ["问题拆解", "核心结论", "健康建议"]
    },
    {
        "category": "健康",
        "question": "我的肠胃不太好，什么时候能调理好？",
        "expected_keywords": ["肠胃", "调理", "健康", "疾病"],
        "expected_structure": ["问题拆解", "核心结论", "调理建议"]
    },
    {
        "category": "家人",
        "question": "我和父母的关系怎么样？需要注意什么？",
        "expected_keywords": ["父母", "家庭关系", "亲情", "家人"],
        "expected_structure": ["问题拆解", "核心结论", "相处建议"]
    },
    {
        "category": "家人",
        "question": "我的兄弟姐妹会给我带来帮助吗？",
        "expected_keywords": ["兄弟姐妹", "帮助", "亲情", "家人"],
        "expected_structure": ["问题拆解", "核心结论", "关系分析"]
    },
    {
        "category": "子女",
        "question": "我什么时候能有孩子？孩子的性格怎么样？",
        "expected_keywords": ["子女", "孩子", "生育", "后代"],
        "expected_structure": ["问题拆解", "核心结论", "子女特征"]
    },
    {
        "category": "子女",
        "question": "我的孩子未来发展怎么样？适合从事什么职业？",
        "expected_keywords": ["子女", "未来发展", "职业", "孩子"],
        "expected_structure": ["问题拆解", "核心结论", "教育建议"]
    },
    {
        "category": "爱人",
        "question": "我的另一半对我事业有帮助吗？",
        "expected_keywords": ["爱人", "伴侣", "事业帮助", "婚姻"],
        "expected_structure": ["问题拆解", "核心结论", "关系分析"]
    },
    {
        "category": "爱人",
        "question": "我和爱人的财运是怎么分配的？谁更会赚钱？",
        "expected_keywords": ["爱人", "财运", "赚钱", "财务"],
        "expected_structure": ["问题拆解", "核心结论", "财务分工"]
    },
]

# 格式检查规则
FORMAT_RULES = {
    "has_markdown_headings": r"^#{2,4}\s",
    "has_bold_keywords": r"\*\*[^*]+\*\*",
    "has_keyword_brackets": r"【[^】]+】",
    "has_hr_separator": r"<hr>",
    "has_ul_list": r"<ul>",
    "has_li_item": r"<li>",
    "has_p_tag": r"<p>",
    "has_strong_tag": r"<strong>",
    "has_summary": r"💡 总结",
    "has_core_conclusion": r"核心结论",
    "invalid_fixed_template": r"未来的剧本已经写好|动态标题|站在\d+年\d+月的节点",
}


async def call_analyze_stream(bazi_data: Dict[str, Any], question: str) -> str:
    """调用AI分析流接口"""
    payload = {
        "birth_date": "2000-01-01",
        "birth_time": "00:00",
        "longitude": 116.4,
        "latitude": 39.9,
        "gender": "男",
        "location": "北京",
        "bazi_data": bazi_data,
        "is_first_reading": False,
        "question": question,
        "history": []
    }
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
        async with session.post(f"{BASE_URL}/api/chat/analyze-stream", json=payload) as response:
            if response.status != 200:
                return f"Error: HTTP {response.status}"
            
            full_content = ""
            async for chunk in response.content.iter_any():
                full_content += chunk.decode('utf-8', errors='replace')
            
            return full_content


def analyze_structure(content: str) -> Dict[str, Any]:
    """分析返回内容的结构"""
    analysis = {
        "has_markdown_headings": bool(re.search(FORMAT_RULES["has_markdown_headings"], content, re.MULTILINE)),
        "has_bold_keywords": bool(re.search(FORMAT_RULES["has_bold_keywords"], content)),
        "has_keyword_brackets": bool(re.search(FORMAT_RULES["has_keyword_brackets"], content)),
        "has_hr_separator": bool(re.search(FORMAT_RULES["has_hr_separator"], content)),
        "has_ul_list": bool(re.search(FORMAT_RULES["has_ul_list"], content)),
        "has_li_item": bool(re.search(FORMAT_RULES["has_li_item"], content)),
        "has_p_tag": bool(re.search(FORMAT_RULES["has_p_tag"], content)),
        "has_strong_tag": bool(re.search(FORMAT_RULES["has_strong_tag"], content)),
        "has_summary": bool(re.search(FORMAT_RULES["has_summary"], content)),
        "has_core_conclusion": bool(re.search(FORMAT_RULES["has_core_conclusion"], content)),
        "has_invalid_template": bool(re.search(FORMAT_RULES["invalid_fixed_template"], content)),
        "heading_count": len(re.findall(FORMAT_RULES["has_markdown_headings"], content, re.MULTILINE)),
        "keyword_bracket_count": len(re.findall(FORMAT_RULES["has_keyword_brackets"], content)),
        "bold_count": len(re.findall(FORMAT_RULES["has_bold_keywords"], content)),
        "hr_count": len(re.findall(FORMAT_RULES["has_hr_separator"], content)),
        "paragraph_count": len(re.findall(FORMAT_RULES["has_p_tag"], content)),
        "word_count": len(content),
        "line_count": len(content.split('\n')),
    }
    
    # 检查问题拆解（子问题列表）
    sub_question_patterns = [
        r"##\s*[一二三四五六七八九十]+、",
        r"###\s*问题\d+",
        r"###\s*【[^】]+】",
    ]
    analysis["has_sub_questions"] = any(re.search(p, content, re.MULTILINE) for p in sub_question_patterns)
    analysis["sub_question_count"] = sum(len(re.findall(p, content, re.MULTILINE)) for p in sub_question_patterns)
    
    return analysis


def evaluate_quality(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """评估返回内容的质量"""
    scores = {}
    
    # 格式规范评分（100分）
    format_score = 100
    
    # 必须包含的元素
    required_elements = [
        "has_markdown_headings",
        "has_bold_keywords",
        "has_keyword_brackets",
        "has_summary",
        "has_core_conclusion",
        "has_sub_questions",
    ]
    
    for element in required_elements:
        if not analysis[element]:
            format_score -= 15
    
    # 禁止的元素
    if analysis["has_invalid_template"]:
        format_score -= 30
    
    # 结构完整性
    if analysis["heading_count"] < 2:
        format_score -= 10
    if analysis["keyword_bracket_count"] < 3:
        format_score -= 10
    
    scores["format_score"] = max(0, format_score)
    
    # 内容丰富度评分（100分）
    content_score = 100
    
    # 字数检查（1000-1800字）
    if analysis["word_count"] < 800:
        content_score -= 30
    elif analysis["word_count"] < 500:
        content_score -= 50
    elif analysis["word_count"] > 2000:
        content_score -= 20
    
    # 段落数检查
    if analysis["paragraph_count"] < 5:
        content_score -= 20
    
    scores["content_score"] = max(0, content_score)
    
    # 综合评分
    scores["overall_score"] = round((scores["format_score"] * 0.6 + scores["content_score"] * 0.4), 1)
    
    # 稳定性评估（基于重复测试）
    scores["quality_level"] = "优秀" if scores["overall_score"] >= 90 else \
                              "良好" if scores["overall_score"] >= 70 else \
                              "一般" if scores["overall_score"] >= 50 else "较差"
    
    return scores


async def run_test() -> Dict[str, Any]:
    """运行完整测试"""
    print("=" * 80)
    print("命理解读API结构测试")
    print("=" * 80)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试八字: {TEST_BAZI_DATA['四柱']}")
    print(f"日主: {TEST_BAZI_DATA['日主']}")
    print(f"年龄: {TEST_BAZI_DATA['年龄']}岁 ({TEST_BAZI_DATA['年龄阶段']})")
    print("=" * 80)
    
    results = {
        "test_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "bazi_info": {
            "四柱": TEST_BAZI_DATA["四柱"],
            "日主": TEST_BAZI_DATA["日主"],
            "年龄": TEST_BAZI_DATA["年龄"],
            "年龄阶段": TEST_BAZI_DATA["年龄阶段"],
        },
        "test_cases": [],
        "summary": {},
    }
    
    # 按类别分组统计
    category_stats = {}
    
    for idx, test_case in enumerate(TEST_CASES, 1):
        print(f"\n--- 测试用例 {idx}/{len(TEST_CASES)} ---")
        print(f"类别: {test_case['category']}")
        print(f"问题: {test_case['question']}")
        
        start_time = time.time()
        content = await call_analyze_stream(TEST_BAZI_DATA, test_case["question"])
        elapsed = round(time.time() - start_time, 2)
        
        print(f"响应时间: {elapsed}秒")
        print(f"内容长度: {len(content)}字")
        
        # 分析结构
        analysis = analyze_structure(content)
        
        # 评估质量
        scores = evaluate_quality(analysis)
        
        # 保存结果
        test_result = {
            "index": idx,
            "category": test_case["category"],
            "question": test_case["question"],
            "response_time": elapsed,
            "word_count": len(content),
            "analysis": analysis,
            "scores": scores,
        }
        results["test_cases"].append(test_result)
        
        # 更新类别统计
        if test_case["category"] not in category_stats:
            category_stats[test_case["category"]] = {
                "count": 0,
                "total_format_score": 0,
                "total_content_score": 0,
                "total_overall_score": 0,
                "total_time": 0,
            }
        category_stats[test_case["category"]]["count"] += 1
        category_stats[test_case["category"]]["total_format_score"] += scores["format_score"]
        category_stats[test_case["category"]]["total_content_score"] += scores["content_score"]
        category_stats[test_case["category"]]["total_overall_score"] += scores["overall_score"]
        category_stats[test_case["category"]]["total_time"] += elapsed
        
        # 打印简要结果
        print(f"格式评分: {scores['format_score']}/100")
        print(f"内容评分: {scores['content_score']}/100")
        print(f"综合评分: {scores['overall_score']}/100")
        print(f"质量等级: {scores['quality_level']}")
        
        # 检查格式问题
        if analysis["has_invalid_template"]:
            print("⚠️ 警告: 使用了禁止的固定模板")
        if not analysis["has_sub_questions"]:
            print("⚠️ 警告: 没有问题拆解")
        if not analysis["has_summary"]:
            print("⚠️ 警告: 没有总结部分")
        if not analysis["has_core_conclusion"]:
            print("⚠️ 警告: 没有核心结论")
    
    # 计算总体统计
    total_format = sum(c["total_format_score"] for c in category_stats.values())
    total_content = sum(c["total_content_score"] for c in category_stats.values())
    total_overall = sum(c["total_overall_score"] for c in category_stats.values())
    total_count = sum(c["count"] for c in category_stats.values())
    total_time = sum(c["total_time"] for c in category_stats.values())
    
    results["summary"] = {
        "total_cases": total_count,
        "avg_format_score": round(total_format / total_count, 1),
        "avg_content_score": round(total_content / total_count, 1),
        "avg_overall_score": round(total_overall / total_count, 1),
        "avg_response_time": round(total_time / total_count, 2),
        "category_stats": {},
    }
    
    # 类别统计
    for category, stats in category_stats.items():
        results["summary"]["category_stats"][category] = {
            "count": stats["count"],
            "avg_format_score": round(stats["total_format_score"] / stats["count"], 1),
            "avg_content_score": round(stats["total_content_score"] / stats["count"], 1),
            "avg_overall_score": round(stats["total_overall_score"] / stats["count"], 1),
            "avg_response_time": round(stats["total_time"] / stats["count"], 2),
        }
    
    # 打印最终总结
    print("\n" + "=" * 80)
    print("测试结果总结")
    print("=" * 80)
    print(f"总测试用例数: {total_count}")
    print(f"平均格式评分: {round(total_format / total_count, 1)}/100")
    print(f"平均内容评分: {round(total_content / total_count, 1)}/100")
    print(f"平均综合评分: {round(total_overall / total_count, 1)}/100")
    print(f"平均响应时间: {round(total_time / total_count, 2)}秒")
    print("\n--- 各类别表现 ---")
    for category, stats in sorted(category_stats.items()):
        avg_overall = round(stats["total_overall_score"] / stats["count"], 1)
        print(f"{category}: {avg_overall}/100 (平均响应: {round(stats['total_time'] / stats['count'], 2)}秒)")
    
    # 保存详细报告
    report_file = f"test_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细报告已保存到: {report_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_test())
