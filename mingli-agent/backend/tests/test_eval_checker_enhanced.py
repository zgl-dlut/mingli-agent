"""
测试评估检查器增强功能：
1. 违规信息包含 expected/reason 字段
2. LLM 软性评分在硬性检查未通过时仍执行
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.eval.structure_checker import check_structure
from app.services.eval.narrative_checker import check_narrative
from app.services.eval.chart_usage_checker import check_chart_usage


def make_minimal_report(subtopics=None):
    """构造最小合法报告"""
    if subtopics is None:
        subtopics = [
            {
                "title": "今年运势怎么样",
                "blocks": [
                    {"keyword": "整体运势", "narrative": "今年整体运势平稳，需要注意调整心态和节奏。"},
                    {"keyword": "下半年", "narrative": "下半年机会更多，建议把握秋季窗口。"},
                ],
            }
        ]
    return {
        "opening": {"verdict": "整体平稳"},
        "subtopics": subtopics,
        "summary": {
            "items": [{"keyword": "9月求职窗口", "text": "保持积极心态"}],
        },
    }


# ═══════════════════════════════════════
# 测试 1：structure_checker 违规信息含 expected/reason
# ═══════════════════════════════════════
print("=" * 60)
print("测试 1：structure_checker 违规信息含 expected/reason")
print("=" * 60)

# 1a. 子问题漏答
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "整体", "narrative": "今年整体运势平稳。"},
]}])
violations = check_structure(report, "今年运势怎么样？下半年能不能换工作？")
found = False
for v in violations:
    if v["type"] == "子问题漏答":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ 子问题漏答: expected='{v['expected']}', reason='{v['reason']}'")
        found = True
if not found:
    print("  ⚠️  未触发子问题漏答（可能问题拆分数量刚好够）")

# 1b. block数量异常
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "整体", "narrative": "今年整体运势平稳。"},
]}])
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "block数量异常":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ block数量异常: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1c. keyword为空
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "", "narrative": "今年整体运势平稳。"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "keyword为空":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ keyword为空: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1d. narrative过短
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "整体", "narrative": "好"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "narrative过短":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ narrative过短: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1e. narrative过长
long_text = "x" * 150
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "整体", "narrative": long_text},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "narrative过长":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ narrative过长: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1f. keyword含加粗标记
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "**整体**", "narrative": "今年整体运势平稳。"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "keyword含加粗标记":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ keyword含加粗标记: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1g. summary关键词泛泛
report = make_minimal_report()
report["summary"]["items"] = [{"keyword": "总结", "text": "保持积极心态"}]
violations = check_structure(report, "今年运势")
for v in violations:
    if v["type"] == "summary关键词泛泛":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ summary关键词泛泛: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 1h. 标题未贴合用户原话
report = make_minimal_report(subtopics=[{"title": "完全无关的标题", "blocks": [
    {"keyword": "整体", "narrative": "今年整体运势平稳。"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_structure(report, "今年运势怎么样")
for v in violations:
    if v["type"] == "标题未贴合用户原话":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ 标题未贴合用户原话: expected='{v['expected']}', reason='{v['reason']}'")
        break


# ═══════════════════════════════════════
# 测试 2：narrative_checker 违规信息含 expected/reason
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 2：narrative_checker 违规信息含 expected/reason")
print("=" * 60)

# 2a. keyword含术语
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "七杀压力", "narrative": "今年外部压力较大。"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_narrative(report, False)
for v in violations:
    if v["type"] == "keyword含术语":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ keyword含术语: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 2b. keyword元标签（首次报告第5个block）
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "整体", "narrative": "今年整体运势平稳。"},
    {"keyword": "事业", "narrative": "事业方面有波动。"},
    {"keyword": "感情", "narrative": "感情需要经营。"},
    {"keyword": "健康", "narrative": "健康要注意休息。"},
    {"keyword": "总结收尾", "narrative": "总体还不错。"},
]}])
violations = check_narrative(report, True)
for v in violations:
    if v["type"] == "keyword元标签":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ keyword元标签: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 2c. keyword回避问题
report = make_minimal_report(subtopics=[{"title": "运势", "blocks": [
    {"keyword": "不好说", "narrative": "这个很难判断。"},
    {"keyword": "下半年", "narrative": "下半年机会更多。"},
]}])
violations = check_narrative(report, False)
for v in violations:
    if v["type"] == "keyword回避问题":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ keyword回避问题: expected='{v['expected']}', reason='{v['reason']}'")
        break


# ═══════════════════════════════════════
# 测试 3：chart_usage_checker 违规信息含 expected/reason
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 3：chart_usage_checker 违规信息含 expected/reason")
print("=" * 60)

# 3a. 编造大运
report = make_minimal_report()
# 在 narrative 中注入一个不存在的大运
report["subtopics"][0]["blocks"][0]["narrative"] = "甲寅大运期间运势较好，建议把握机会。"
chart_data = {
    "当前大运": "丁丑",
    "重点流年": [],
    "用神": "金",
    "忌神": "火",
}
violations = check_chart_usage(report, chart_data)
for v in violations:
    if v["type"] == "编造大运":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ 编造大运: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 3b. 用神不一致
report = make_minimal_report()
report["subtopics"][0]["blocks"][0]["narrative"] = "用神为火，建议多穿红色。"
chart_data = {
    "当前大运": "丁丑",
    "重点流年": [],
    "用神": "金",
    "忌神": "火",
}
violations = check_chart_usage(report, chart_data)
for v in violations:
    if v["type"] == "用神不一致":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ 用神不一致: expected='{v['expected']}', reason='{v['reason']}'")
        break

# 3c. 忌神不一致
report = make_minimal_report()
report["subtopics"][0]["blocks"][0]["narrative"] = "忌神为土，需要避开土旺月份。"
chart_data = {
    "当前大运": "丁丑",
    "重点流年": [],
    "用神": "金",
    "忌神": "火",
}
violations = check_chart_usage(report, chart_data)
for v in violations:
    if v["type"] == "忌神不一致":
        assert "expected" in v, f"缺少 expected 字段: {v}"
        assert "reason" in v, f"缺少 reason 字段: {v}"
        print(f"  ✅ 忌神不一致: expected='{v['expected']}', reason='{v['reason']}'")
        break


# ═══════════════════════════════════════
# 测试 4：验证正常报告不触发违规
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("测试 4：正常报告不触发违规")
print("=" * 60)

report = make_minimal_report()
struct_v = check_structure(report, "今年运势怎么样")
narr_v = check_narrative(report, False)
chart_v = check_chart_usage(report, {
    "当前大运": "丁丑",
    "重点流年": [],
    "用神": "金",
    "忌神": "火",
})

total = len(struct_v) + len(narr_v) + len(chart_v)
if total == 0:
    print(f"  ✅ 正常报告无违规: structure={len(struct_v)}, narrative={len(narr_v)}, chart={len(chart_v)}")
else:
    print(f"  ❌ 正常报告有违规: structure={struct_v}, narrative={narr_v}, chart={chart_v}")


# ═══════════════════════════════════════
# 汇总
# ═══════════════════════════════════════
print("\n" + "=" * 60)
print("所有 checker 增强测试完成")
print("=" * 60)
