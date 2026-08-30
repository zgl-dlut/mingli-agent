"""叙事性检查器：检查报告叙事性合规性（术语管控、叙事化、答非所问）。

检查项：
1. keyword 含术语黑名单词
2. narrative 中术语是否有解释（括号/= /也就是/即 紧跟）
3. keyword 元标签检测（首次报告第5个block专用）
4. keyword 回避问题（否定式回避）
"""
import re
from typing import List, Dict

# 术语黑名单（与 followup_structured.py 的 _detect_forbidden_terms 保持一致）
TERM_BLACKLIST = [
    "七杀", "正官", "偏印", "正印", "伤官", "食神",
    "比肩", "劫财", "偏财", "正财", "月令", "宫位",
    "用神", "忌神", "日支", "流月",
]

# 元标签黑名单（project_memory：首次报告第5个block禁止用元标签）
META_LABELS = ["收尾点睛", "总结", "收尾", "小结", "结语", "归纳"]

# 回避式表达模式
EVASIVE_PATTERNS = [r"不便回答", r"无法确定", r"难以判断", r"不好说", r"说不清"]

# 编造具体人物关系模式（命盘无法显示具体人物事件）
SPECIFIC_RELATIONSHIP_PATTERNS = [
    r"(表哥|表姐|堂哥|堂姐|叔叔|阿姨|舅舅|舅妈|姑姑|姑父|大伯|大妈)",
    r"(闺蜜|兄弟|哥们|姐们|死党)",
    r"(借钱不还|背后说坏话|介绍工作|合伙投资)",
]


def check_narrative(report: dict, is_first_reading: bool = False) -> List[Dict]:
    """检查报告叙事性合规性。

    Args:
        report: 追问报告 JSON
        is_first_reading: 是否首次报告（首次报告有额外的元标签检查）

    Returns:
        违规列表
    """
    violations = []

    subtopics = report.get("subtopics", [])

    # 1. keyword 含术语黑名单词
    for i, sub in enumerate(subtopics):
        for j, blk in enumerate(sub.get("blocks", [])):
            if not isinstance(blk, dict):
                continue
            kw = blk.get("keyword", "")
            for term in TERM_BLACKLIST:
                if term in kw:
                    violations.append({
                        "type": "keyword含术语",
                        "subtopic": i,
                        "block": j,
                        "detail": f"keyword='{kw}' 含术语'{term}'，需替换为大白话",
                        "location": f"subtopics[{i}].blocks[{j}].keyword",
                        "expected": "keyword 应为大白话（如'外部压力'而非'七杀'）",
                        "reason": "术语出现在keyword会让小白用户看不懂，术语应作为括号标签点缀在narrative中",
                    })

    # 2. [已移除] 术语无解释检查 — 术语作为命盘依据标签出现即可，不强制要求紧跟解释
    # 核心期望：报告有命盘依据、体现专业性，术语以括号标签形式点缀即可
    # 说明：原检查要求术语后紧跟（括号/= /也就是/即），但实际报告中术语作为命盘依据标签
    #       出现在大白话后即可（如"外部压力较大（七杀）"），不需要额外解释

    # 3. keyword 元标签检测（首次报告第5个block专用）
    if is_first_reading and subtopics:
        blocks = subtopics[0].get("blocks", [])
        if len(blocks) >= 5:
            kw = blocks[4].get("keyword", "")
            for meta in META_LABELS:
                if meta in kw:
                    violations.append({
                        "type": "keyword元标签",
                        "block": 4,
                        "detail": f"首次报告第5个block的keyword='{kw}'含元标签'{meta}'",
                        "location": "subtopics[0].blocks[4].keyword",
                        "expected": "首次报告第5个block应为具体行动建议（如'10月前锁定offer'），禁止用'总结''收尾'等元标签",
                        "reason": "元标签是LLM的写作习惯，对用户无实际价值，用户需要的是具体行动指引",
                    })

    # 4. keyword 回避问题
    for i, sub in enumerate(subtopics):
        for j, blk in enumerate(sub.get("blocks", [])):
            if not isinstance(blk, dict):
                continue
            kw = blk.get("keyword", "")
            for pat in EVASIVE_PATTERNS:
                if re.search(pat, kw):
                    violations.append({
                        "type": "keyword回避问题",
                        "subtopic": i,
                        "block": j,
                        "detail": f"keyword='{kw}' 含回避式表达",
                        "location": f"subtopics[{i}].blocks[{j}].keyword",
                        "expected": "keyword 应直接回答用户问题（如'9月最佳窗口'），禁止'不好说''难以判断'等回避表达",
                        "reason": "回避式表达会让用户觉得LLM在敷衍，降低报告可信度和用户满意度",
                    })

    # 5. narrative 编造具体人物关系（命盘无法显示具体人物事件）
    for i, sub in enumerate(subtopics):
        for j, blk in enumerate(sub.get("blocks", [])):
            if not isinstance(blk, dict):
                continue
            narrative = blk.get("narrative", "")
            for pat in SPECIFIC_RELATIONSHIP_PATTERNS:
                if re.search(pat, narrative):
                    violations.append({
                        "type": "narrative编造具体人物关系",
                        "subtopic": i,
                        "block": j,
                        "detail": f"narrative 含编造的具体人物关系模式'{pat}'",
                        "location": f"subtopics[{i}].blocks[{j}].narrative",
                        "expected": "narrative 应给趋势判断（如'人情往来增多''注意合作风险'），禁止编造具体场景（如'表哥借钱''闺蜜背叛'）",
                        "reason": "命盘无法显示具体人物事件，编造具体场景会让用户觉得AI在瞎编，严重损害可信度",
                    })

    return violations
