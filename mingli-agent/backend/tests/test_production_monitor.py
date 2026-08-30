"""测试生产监控智能采样策略"""
import sys
sys.path.insert(0, '.')

from app.services.eval.production_monitor import (
    should_deep_eval,
    _check_sensitive_topic,
    _check_negative_emotion,
    _check_light_metrics,
    _check_rule_violations,
    _count_chinese_chars,
    _extract_report_text,
)

# ─── 辅助：构造最小合法报告 ───
def make_report(subtopics=None, opening_verdict="", summary_items=None, word_count=500):
    """构造一个最小合法报告，可控制字数"""
    blocks = []
    if word_count > 0:
        # 用重复文字凑字数
        filler = "今年整体运势平稳，需要注意调整心态和节奏，保持积极乐观的态度面对生活中的各种挑战。"
        needed = max(1, word_count // len(filler) + 1)
        text = (filler * needed)[:word_count]
        blocks.append({"type": "keyword", "keyword": "整体运势", "narrative": text})

    if subtopics is None:
        subtopics = [{"title": "测试子问题", "blocks": blocks}]

    return {
        "opening": {"verdict": opening_verdict or "整体平稳"},
        "subtopics": subtopics,
        "summary": {
            "items": summary_items or [{"keyword": "总结", "text": "保持积极心态"}],
        },
    }


# ══════════════════════════════════════
# 测试 1：敏感话题检测
# ═══════════════════════════════════════
print("=" * 60)
print("测试 1：敏感话题检测")
print("=" * 60)

test_cases_sensitive = [
    ("我今年能换工作吗", False, "普通问题"),
    ("我最近身体不好，会不会得大病", True, "健康类"),
    ("我打算创业开店，时机对吗", True, "投资类"),
    ("我和他有法律纠纷，能赢吗", True, "法律类"),
    ("我最近很焦虑，感觉撑不下去了", True, "心理类"),
    ("今年财运怎么样", False, "普通财运"),
    ("我想做手术，什么时候合适", True, "手术"),
]

for question, expected, desc in test_cases_sensitive:
    result, reason = _check_sensitive_topic(question)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {desc}: '{question}' -> {result} (预期 {expected})")
    if result:
        print(f"     原因: {reason}")

# ═══════════════════════════════════════
# 测试 2：负面情绪检测
# ══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 2：负面情绪检测")
print("=" * 60)

test_cases_emotion = [
    ("我该怎么办，好烦啊", True, "焦虑"),
    ("最近好累，受不了了", True, "疲惫"),
    ("感觉没救了，完了", True, "绝望"),
    ("今年运势怎么样", False, "中性"),
    ("想换工作，有什么建议", False, "普通"),
]

for question, expected, desc in test_cases_emotion:
    result, reason = _check_negative_emotion(question)
    status = "✅" if result == expected else "❌"
    print(f"  {status} {desc}: '{question}' -> {result} (预期 {expected})")

# ═══════════════════════════════════════
# 测试 3：轻量指标检测
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 3：轻量指标检测")
print("=" * 60)

# 正常报告
normal_report = make_report(word_count=600)
signals = _check_light_metrics(normal_report, 30.0)
print(f"  {'✅' if not signals else '❌'} 正常报告(600字,30s): {signals or '无异常'}")

# 字数过少
short_report = make_report(word_count=100)
signals = _check_light_metrics(short_report, 30.0)
print(f"  {'✅' if signals else '❌'} 字数过少(100字): {signals}")

# 生成过快
fast_report = make_report(word_count=600)
signals = _check_light_metrics(fast_report, 1.0)
print(f"  {'✅' if signals else '❌'} 生成过快(1s): {signals}")

# block 过少
empty_report = {"opening": {"verdict": "ok"}, "subtopics": [{"title": "t", "blocks": []}], "summary": {"items": []}}
signals = _check_light_metrics(empty_report, 30.0)
print(f"  {'✅' if signals else '❌'} block 过少(0): {signals}")

# ═══════════════════════════════════════
# 测试 4：规则违规检测
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 4：规则违规检测")
print("=" * 60)

# 含术语违规
term_report = {
    "opening": {"verdict": "ok"},
    "subtopics": [{"title": "t", "blocks": [{"type": "keyword", "keyword": "运势", "narrative": "今年杀印相生，运势好转"}]}],
    "summary": {"items": []},
}
violations = _check_rule_violations(term_report)
print(f"  {'✅' if violations else '❌'} 术语违规(杀印相生): {violations}")

# 含干支纪时
gz_report = {
    "opening": {"verdict": "ok"},
    "subtopics": [{"title": "t", "blocks": [{"type": "keyword", "keyword": "时间", "narrative": "丁酉月要注意身体"}]}],
    "summary": {"items": []},
}
violations = _check_rule_violations(gz_report)
print(f"  {'✅' if violations else '❌'} 干支纪时(丁酉月): {violations}")

# 正常报告
clean_report = make_report(word_count=500)
violations = _check_rule_violations(clean_report)
print(f"  {'✅' if not violations else '❌'} 正常报告: {violations or '无违规'}")

# ═══════════════════════════════════════
# 测试 5：完整采样决策
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 5：完整采样决策 should_deep_eval")
print("=" * 60)

test_decisions = [
    # (report, question, is_first, gen_time, rule_violations, expected_trigger_contains)
    (make_report(), "我今年能换工作吗", False, 30.0, None, ""),  # 普通追问 -> 不触发(大概率)
    (make_report(), "我最近身体不好会不会得大病", False, 30.0, None, "sensitive_topic"),  # 敏感
    (make_report(), "今年运势怎么样", True, 30.0, None, "first_report"),  # 首次报告
    (make_report(word_count=100), "今年运势", False, 30.0, None, "light_metric"),  # 字数过少
    (make_report(), "今年运势", False, 30.0, ["术语违规: 杀印相生"], "rule_violation"),  # 规则违规
    (make_report(), "我该怎么办好烦啊", False, 30.0, None, "negative_emotion"),  # 负面情绪
]

for report, question, is_first, gen_time, rule_v, expected in test_decisions:
    result, reason = should_deep_eval(report, question, is_first, gen_time, rule_v)
    if expected:
        status = "✅" if expected in reason else "❌"
        print(f"  {status} '{question[:30]}' -> {result}, reason={reason} (预期包含 {expected})")
    else:
        # 随机采样有 5% 概率触发，所以不强制检查
        print(f"  ℹ️  '{question[:30]}' -> {result}, reason={reason} (普通追问，可能随机触发)")

# ═══════════════════════════════════════
# 测试 6：中文字符统计
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 6：中文字符统计")
print("=" * 60)

tests = [
    ("你好世界", 4),
    ("hello世界", 2),
    ("123abc", 0),
    ("今年整体运势平稳", 8),
]
for text, expected in tests:
    result = _count_chinese_chars(text)
    status = "✅" if result == expected else "❌"
    print(f"  {status} '{text}' -> {result} (预期 {expected})")

# ═══════════════════════════════════════
# 汇总
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
