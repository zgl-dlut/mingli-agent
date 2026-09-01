"""结构检查器：检查报告 JSON 结构是否符合 schema 约束和 project_memory 规则。

检查项：
1. 子问题拆解覆盖度（用户问了几个独立点，subtopic 数量是否足够）
2. 每个 subtopic 的 blocks 数量（2-4）
3. 每个 block 的 keyword 非空、narrative 字数 30-120
4. keyword 不加 **（加粗在 narrative 内联）
5. summary items 的 keyword 叙事化（禁止泛泛标签）
6. subtopic 标题贴合用户原话
"""
import re
from typing import List, Dict


# 连词识别列表（用于估算独立关切点）
_CONNECTORS = ["和", "与", "还有", "另外", "以及", "同时", "是否", "能不能", "能不能够", "还是"]

# 泛泛标签模式（project_memory：禁止"蹲守期/守业期/蛰伏期"等）
_GENERIC_PATTERNS = [
    r"^[蛰伏蹲守守业过渡调整观望伏期守业期过渡期观望期]+期?$",
    r"^[总结收尾点睛小结结语归纳]+$",
]

# 停用词列表（用于关键词提取过滤）
_STOP_WORDS = {
    "的", "了", "是", "有", "一", "在", "吗", "呢", "吧", "啊", "哦", "呀",
    "和", "与", "或", "及", "还", "也", "都", "就", "才", "又", "再", "更",
    "这", "那", "哪", "什么", "怎么", "如何", "为什么", "是否", "能不能",
    "可以", "应该", "需要", "想要", "希望", "觉得", "认为", "知道", "了解",
    "关于", "对于", "因为", "所以", "虽然", "但是", "如果", "那么", "然后",
    "或者", "还是", "以及", "另外", "同时", "而且", "不过", "只是", "已经",
    "正在", "将会", "可能", "大概", "也许", "应该", "必须", "务必",
    "的", "地", "得", "着", "过", "们", "个", "些", "点", "次", "回",
    "上", "下", "里", "外", "中", "间", "前", "后", "左", "右",
    "我", "你", "他", "她", "它", "我们", "你们", "他们", "她们",
    "这个", "那个", "哪个", "这些", "那些", "哪些",
    "吗", "呢", "吧", "啊", "哦", "呀", "哇", "哎", "嗯",
    "是不是", "有没有", "能不能", "会不会", "对不对", "好不好",
}


def estimate_question_count(question: str) -> int:
    """估算用户问题中的独立关切点数量。

    按标点切分 + 连词识别，上限 4（project_memory 建议拆 2-4 个）。
    """
    segments = re.split(r'[，。？；！]', question)
    segments = [s.strip() for s in segments if s.strip()]
    count = 0
    for seg in segments:
        for conn in _CONNECTORS:
            if conn in seg:
                count += 1
                break  # 一个 segment 内只计一次连词
        count += 1
    return min(max(1, count), 4)


def extract_question_keywords(question: str) -> List[str]:
    """提取用户问题中的关键词（用于标题贴合度检查）。

    优化逻辑：
    1. 按标点和停用词切分问题为片段
    2. 从每个片段提取 2-6 字符的有效词
    3. 过滤纯虚词组合
    4. 去重，最多返回 10 个
    """
    # 构建切分模式：标点 + 停用词
    stop_pattern = r'[，。？；！、\s]+' + r'|'.join(re.escape(sw) for sw in _STOP_WORDS if len(sw) >= 2)
    segments = re.split(stop_pattern, question)

    keywords = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # 从片段中提取 2-6 字符的有效词
        words = re.findall(r'[\u4e00-\u9fa50-9]{2,6}', seg)
        for w in words:
            # 过滤纯虚词组合
            non_digit = [c for c in w if c not in "0123456789"]
            if non_digit and all(c in "的了是在有吗呢吧啊哦呀" for c in non_digit):
                continue
            keywords.append(w)

    # 去重，优先保留较长的关键词
    seen = set()
    unique = []
    keywords.sort(key=len, reverse=True)
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:10]


def check_structure(report: dict, user_question: str, is_first_reading: bool = False) -> List[Dict]:
    """检查报告结构合规性。

    Args:
        report: 追问报告 JSON（FollowupReport 结构）
        user_question: 用户原始问题
        is_first_reading: 是否首次报告（首次报告用户仅输入生辰无具体问题、subtopic 标题固定，
            跳过"标题未贴合用户原话"校验；追问报告保留该校验）

    Returns:
        违规列表，每项 {"type": str, "detail": str, "location": str}
    """
    violations = []

    # 1. 子问题拆解覆盖度
    expected = estimate_question_count(user_question)
    subtopics = report.get("subtopics", [])
    actual = len(subtopics)
    if actual < max(1, int(expected * 0.8)):
        violations.append({
            "type": "子问题漏答",
            "detail": f"用户约{expected}个独立点，只拆了{actual}个",
            "location": "subtopics",
            "expected": f"至少{max(1, int(expected * 0.8))}个subtopic（用户问题含{expected}个独立关切点）",
            "reason": "用户问了多个独立问题但报告未逐一拆解回答，会导致部分问题被遗漏",
        })

    # 2. 每个 subtopic 的 blocks 数量（追问2-4，首次2-6）
    _MAX_BLOCKS = 6 if is_first_reading else 4
    for i, sub in enumerate(subtopics):
        blocks = [b for b in sub.get("blocks", []) if isinstance(b, dict)]
        if len(blocks) < 2 or len(blocks) > _MAX_BLOCKS:
            violations.append({
                "type": "block数量异常",
                "subtopic": i,
                "detail": f"blocks={len(blocks)}，应为2-{_MAX_BLOCKS}",
                "location": f"subtopics[{i}].blocks",
                "expected": f"每个subtopic包含2-{_MAX_BLOCKS}个blocks（首次报告内容多放宽上限）",
                "reason": "block过少则论述不充分，过多则碎片化，2-4是追问最佳节奏，首次报告放宽到2-6",
            })

    # 3. 每个 block 的 keyword 非空、narrative 字数（30-130，首次报告放宽到30-160）
    _MAX_NAR = 160 if is_first_reading else 130
    for i, sub in enumerate(subtopics):
        for j, blk in enumerate(sub.get("blocks", [])):
            if not isinstance(blk, dict):
                continue
            kw = blk.get("keyword", "")
            nar = blk.get("narrative", "")
            if not kw.strip():
                violations.append({
                    "type": "keyword为空",
                    "subtopic": i,
                    "block": j,
                    "detail": "keyword 字段为空",
                    "location": f"subtopics[{i}].blocks[{j}].keyword",
                    "expected": "keyword 应为2-6字的大白话短语（如'4月涨薪'）",
                    "reason": "keyword为空会导致前端无法渲染block标题，用户看不到分段逻辑",
                })
            if len(nar) < 5:
                violations.append({
                    "type": "narrative过短",
                    "subtopic": i,
                    "block": j,
                    "detail": f"narrative={len(nar)}字，最少5字",
                    "location": f"subtopics[{i}].blocks[{j}].narrative",
                    "expected": "narrative 至少5字，建议30字以上",
                    "reason": "narrative过短说明该block没有实质内容，可能是LLM偷懒跳过",
                })
            if len(nar) > _MAX_NAR:
                violations.append({
                    "type": "narrative过长",
                    "subtopic": i,
                    "block": j,
                    "detail": f"narrative={len(nar)}字，最多{_MAX_NAR}字",
                    "location": f"subtopics[{i}].blocks[{j}].narrative",
                    "expected": f"narrative 最多{_MAX_NAR}字，建议30字以上",
                    "reason": "narrative过长会导致手机端阅读体验差，应拆成多个block",
                })

    # 4. keyword 加粗检查（keyword 字段本身不加 **）
    for i, sub in enumerate(subtopics):
        for j, blk in enumerate(sub.get("blocks", [])):
            if not isinstance(blk, dict):
                continue
            kw = blk.get("keyword", "")
            if "**" in kw:
                violations.append({
                    "type": "keyword含加粗标记",
                    "subtopic": i,
                    "block": j,
                    "detail": f"keyword 不应含 **，加粗应在 narrative 内联",
                    "location": f"subtopics[{i}].blocks[{j}].keyword",
                    "expected": "keyword 为纯文本，加粗标记 ** 应放在 narrative 字段内的关键词上",
                    "reason": "keyword 是前端渲染的标签，含 ** 会导致显示异常",
                })

    # 5. summary items 的 keyword 叙事化（禁止泛泛标签）
    summary = report.get("summary", {})
    for item in summary.get("items", []):
        if not isinstance(item, dict):
            continue
        kw = item.get("keyword", "")
        for pat in _GENERIC_PATTERNS:
            if re.match(pat, kw):
                violations.append({
                    "type": "summary关键词泛泛",
                    "detail": f"keyword='{kw}' 使用泛泛标签，需'时间+具体事件'格式",
                    "location": "summary.items",
                    "expected": "summary keyword 应为'时间+具体事件'格式（如'9月求职窗口'）",
                    "reason": "泛泛标签（如'总结''收尾'）无法给用户提供具体行动指引",
                })
                break

    # 6. subtopic 标题贴合用户原话（首次报告用户仅输入生辰无具体问题、标题固定，跳过该校验；追问保留）
    if is_first_reading:
        return violations
    question_keywords = extract_question_keywords(user_question)
    # 也提取问题中的有意义单字（用于字符级重叠检查）
    question_chars = set(c for c in user_question if c not in "的了是在有吗呢吧啊哦呀和与或及还也都就又再更这那哪什么怎么如何是否能不能可以应该需要想要希望觉得认为知道了解关于对于因为所以虽然但是如果那么然后或者还是以及另外同时而且不过只是已经正在将会可能大概也许必须务必的地得着过们个些点次回上下里外中间前后左右我你他她它我们你们他们她们这个那个哪个这些那些哪些是不是有没有能不能会不会对不对好不好")
    
    for i, sub in enumerate(subtopics):
        title = sub.get("title", "")
        # 关键词级重叠
        keyword_overlap = len([k for k in question_keywords if k in title])
        # 字符级重叠（至少有 2 个有意义的字重叠）
        title_chars = set(title)
        char_overlap = len(question_chars & title_chars)
        
        if keyword_overlap == 0 and char_overlap < 2 and question_keywords:
            violations.append({
                "type": "标题未贴合用户原话",
                "subtopic": i,
                "detail": f"title='{title}' 与用户问题关键词/字符重叠不足 (关键词重叠={keyword_overlap}, 字符重叠={char_overlap})",
                "location": f"subtopics[{i}].title",
                "expected": "subtopic标题应包含用户问题中的关键词（如用户问'几月离职'，标题应含'离职'）",
                "reason": "标题与用户问题脱节会让用户觉得答非所问，降低信任感",
            })

    return violations
