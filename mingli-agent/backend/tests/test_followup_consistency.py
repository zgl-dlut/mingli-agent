"""
错误追问摘要不影响命盘结论的保障测试

分两层：
1. 单元测试（纯函数，不调LLM，快、稳定）：
   - prompt 措辞保障：确认"命盘权威/以命盘为准/不盲从前轮/严禁编造"等修复措辞进了 prompt
   - 历史摘要提取逻辑：确认 verdict/子问题标题提取正确，Markdown 首次报告被跳过
2. 集成测试（调LLM，需API key，自动从 .env 加载）：
   - 注入与命盘矛盾的"错误历史摘要"，验证 LLM 仍以命盘为准，不盲从、不编造

背景：修复"一致性要求"措辞前，错误历史摘要会让 LLM 盲从前轮结论，甚至编造反命盘的
命理依据（如命盘忌火却编造"大运助金水"说适合创业）。本测试固化修复效果，防止回归。
"""
import sys
import os
import json
import asyncio
import urllib.request

import pytest

# 添加 backend 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.followup_structured import build_structured_prompt, _build_history_summary, _extract_and_fix_json

def _build_prompt(*args, **kwargs):
    """同步包装 async 的 build_structured_prompt，供测试调用"""
    return asyncio.run(build_structured_prompt(*args, **kwargs))

from app.services.report_styles import (
    OPENING_STYLES, SUMMARY_STYLES, RECENT_WINDOW, pick_styles, _collect_used_styles,
)

# 尝试加载 .env（集成测试需要 API key）
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass


# ============================================================
# 固定命盘：壬水弱，2027丁未年火土忌神当道（不利创业）
# 错误历史摘要会说"适合创业"，与命盘矛盾，用于验证 LLM 是否盲从
# ============================================================

FIXED_CONTEXT = {
    "current_time": "2026年8月",
    "liunian_ganzhi": "丙午",
    "liunian_season": "夏季",
    "sizu": "壬申 庚戌 壬子 辛亥",
    "rizhu": "壬水",
    "gender": "男",
    "wangshuai": "偏弱",
    "geju_description": "印格",
    "yongshen": "金水（帮身）",
    "xishen": "金水",
    "jishen": "火土（耗身）",
    "shishen_fenbu": "偏印/正印/比肩/劫财",
    "wuxing_fenbu": "水4 金3 土2 火1 木1",
    "dizhi_zuoyong": "申子半合水局",
    "tiaohou_desc": "调候需金水润局",
    "current_dayun": "丙午",
    "dayun_jiedu": "火土忌神运，耗身破财",
    "key_liunian": "2027丁未年：丁火透干+未土，火土忌神当道，对弱水日主不利，耗身破财",
    "user_question": "2027年我适合创业吗？",
    "age": 35,
    "birth_year": 1991,
    "age_stage": "中年期（31-50岁）",
}

# 与命盘矛盾的"错误历史摘要"
WRONG_HISTORY = "第1轮回答：核心结论：2027丁未年是你事业爆发期，适合创业扩张，大吉"

# 与命盘一致的"正确历史摘要"（对照组）
RIGHT_HISTORY = "第1轮回答：核心结论：2027丁未年火土忌神当道，宜守不宜攻"


# ============================================================
# 单元测试 1：prompt 措辞保障（不调LLM）
# ============================================================

class TestPromptConsistencyRules:
    """验证修复后的"命盘权威"措辞确实进了 system_prompt"""

    def test_prompt_has_panpan_authority(self):
        """命盘数据是最高推演依据"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "命盘数据是最高推演依据" in prompt

    def test_prompt_allows_correction(self):
        """以命盘为准可修正前轮"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "以命盘为准" in prompt

    def test_prompt_forbids_blind_follow(self):
        """不盲从惯性判断（禁止复用前轮式断语）"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "不盲从惯性判断" in prompt

    def test_prompt_forbids_fabrication(self):
        """严禁编造命理依据"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "严禁编造命理依据" in prompt

    def test_prompt_no_must_keep_consistent(self):
        """旧措辞'必须保持一致，禁止自相矛盾'已移除（避免强制盲从）"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "必须与历史摘要保持一致，禁止自相矛盾" not in prompt

    def test_prompt_injects_history_when_present(self):
        """有历史摘要时，摘要区块注入 prompt（新：只含用户问题，不含AI断语）"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "此前对话话题" in prompt
        # WRONG_HISTORY 是模拟摘要文本（外部传入），区块本身不携带结论性规则
        assert "没有任何历史结论" in prompt

    def test_prompt_no_history_section_when_empty(self):
        """空历史时不应出现历史摘要区块"""
        prompt = _build_prompt(FIXED_CONTEXT, "")
        assert "此前对话话题" not in prompt

    def test_prompt_keeps_bazi_data(self):
        """命盘数据完整注入（以命盘为准的前提）"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        assert "壬水" in prompt
        assert "金水" in prompt  # 用神
        assert "火土" in prompt  # 忌神
        assert "2027丁未年" in prompt  # 重点流年


# ============================================================
# 单元测试 2：历史摘要提取逻辑（不调LLM）
# ============================================================

class TestHistorySummaryExtraction:
    """验证 _build_history_summary 的新行为：只含用户问题，绝不携带AI断语"""

    def test_excludes_assistant_verdict(self):
        """assistant 结论（verdict/title/items）一律不进摘要——根治编造传染"""
        history = [{"role": "assistant", "content": json.dumps({
            "opening": {"verdict": "2027年不宜创业"},
            "subtopics": [{"title": "财务时间线"}, {"title": "离职时机"}],
            "summary": {"title": "总结", "items": [
                {"keyword": "9月", "text": "打磨作品集"},
            ]},
        }, ensure_ascii=False)}]
        summary = _build_history_summary(history)
        assert summary == ""
        assert "2027年不宜创业" not in summary
        assert "财务时间线" not in summary
        assert "打磨作品集" not in summary

    def test_extracts_user_questions(self):
        """用户历史问题进摘要（天然无编造）"""
        history = [{"role": "user", "content": "27年适合跳槽吗？"}]
        summary = _build_history_summary(history)
        assert "27年适合跳槽吗" in summary
        assert "不含任何结论" in summary

    def test_skips_markdown_first_reading(self):
        """Markdown 首次报告不进摘要（同旧行为，防错误传染）"""
        history = [{"role": "assistant", "content": "# 你的命理全局解读\n\n壬水日主偏弱，2027年适合创业扩张..."}]
        summary = _build_history_summary(history)
        assert summary == ""
        assert "适合创业扩张" not in summary

    def test_skips_user_messages(self):
        """改为：user 消息正是摘要来源，assistant 断语被跳过"""
        history = [
            {"role": "user", "content": "用户原始问题"},
            {"role": "assistant", "content": json.dumps({
                "opening": {"verdict": "虚构断语XYZ"},
                "subtopics": [], "summary": {"title": "s"},
            }, ensure_ascii=False)},
        ]
        summary = _build_history_summary(history)
        assert "用户原始问题" in summary
        assert "虚构断语XYZ" not in summary

    def test_empty_history_returns_empty(self):
        """空历史返回空字符串"""
        assert _build_history_summary([]) == ""

    def test_invalid_json_skipped(self):
        """无效 JSON 的 assistant 消息被跳过（不抛异常）"""
        history = [{"role": "assistant", "content": "这不是JSON"}]
        assert _build_history_summary(history) == ""

    def test_long_question_truncated(self):
        """超长用户问题截断到80字"""
        history = [{"role": "user", "content": "长" * 200}]
        summary = _build_history_summary(history)
        assert "…" in summary
        assert len(summary) < 200


# ============================================================
# 单元测试 3：后端风格轮换（不调LLM）
# ============================================================

def _make_report(opening_style_key=None, summary_style_key=None) -> dict:
    """构造一份带 style_key 盖章的历史报告消息"""
    report = {
        "opening": {"lead": "开头文案", "verdict": "核心结论"},
        "subtopics": [{"title": "子问题", "blocks": [{"type": "keyword", "keyword": "k", "narrative": "n"}]}],
        "summary": {"title": "总结"},
    }
    if opening_style_key:
        report["opening"]["style_key"] = opening_style_key
    if summary_style_key:
        report["summary"]["style_key"] = summary_style_key
    return {"role": "assistant", "content": json.dumps(report, ensure_ascii=False)}


class TestStyleRotation:
    """验证后端风格轮换：pick_styles 排除最近已用风格 + prompt 只注入选中风格"""

    def test_empty_history_returns_valid_styles(self):
        """空历史：返回库内合法风格"""
        opening, summary = pick_styles([])
        assert opening[0] in OPENING_STYLES
        assert opening[1] == OPENING_STYLES[opening[0]]
        assert summary[0] in SUMMARY_STYLES
        assert summary[1] == SUMMARY_STYLES[summary[0]]

    def test_excludes_recent_used_styles(self):
        """最近 3 轮已用风格被排除"""
        used_opening = list(OPENING_STYLES)[:3]
        used_summary = list(SUMMARY_STYLES)[:3]
        history = [
            _make_report(o, s) for o, s in zip(used_opening, used_summary)
        ]
        for _ in range(20):  # 多次随机采样，均不得命中已用风格
            opening, summary = pick_styles(history)
            assert opening[0] not in used_opening, f"开头风格重复: {opening[0]}"
            assert summary[0] not in used_summary, f"总结风格重复: {summary[0]}"

    def test_window_capped_at_recent_window(self):
        """排除窗口上限为 RECENT_WINDOW：更早的已用风格可再次选用"""
        opening_names = list(OPENING_STYLES)
        # 造 RECENT_WINDOW+2 轮历史，最老 2 轮的风格超出窗口
        history = [
            _make_report(opening_names[i % len(opening_names)], None)
            for i in range(RECENT_WINDOW + 2)
        ]
        used_opening, _ = _collect_used_styles(history, RECENT_WINDOW)
        # 窗口内最多收集 RECENT_WINDOW 个（倒序截断），最老的不在排除集
        assert opening_names[0] not in used_opening
        assert opening_names[1] not in used_opening

    def test_legacy_history_without_style_key(self):
        """旧消息无 style_key：不报错、不纳入排除"""
        history = [_make_report(None, None), {"role": "assistant", "content": "纯Markdown旧报告"}]
        used_opening, used_summary = _collect_used_styles(history, RECENT_WINDOW)
        assert used_opening == set()
        assert used_summary == set()
        opening, summary = pick_styles(history)  # 不抛异常
        assert opening[0] in OPENING_STYLES
        assert summary[0] in SUMMARY_STYLES

    def test_prompt_injects_only_selected_styles(self):
        """prompt 只注入选中的那一条风格（尾部'本轮风格要求'），未选中风格名不出现"""
        opening = ("痛点直击式", OPENING_STYLES["痛点直击式"])
        summary = ("时间轴", SUMMARY_STYLES["时间轴"])
        prompt = _build_prompt(FIXED_CONTEXT, "", opening_style=opening, summary_style=summary)
        assert "## 本轮风格要求" in prompt
        assert f"开头风格：**痛点直击式**（{OPENING_STYLES['痛点直击式']}）" in prompt
        assert f"总结风格：**时间轴**（{SUMMARY_STYLES['时间轴']}）" in prompt
        # 未选中的风格名不出现在 prompt（省 token 的核心验证）
        for name in OPENING_STYLES:
            if name != "痛点直击式":
                assert name not in prompt, f"未选中开头风格'{name}'泄漏进prompt"
        for name in SUMMARY_STYLES:
            if name != "时间轴":
                assert name not in prompt, f"未选中总结风格'{name}'泄漏进prompt"

    def test_history_summary_no_style_hints(self):
        """历史摘要不再注入'上次开头句式/上次总结风格'提示（轮换由后端保证）"""
        history = [_make_report("现状承接式", "行动清单")]
        summary = _build_history_summary(history)
        assert "上次开头句式" not in summary
        assert "上次总结风格" not in summary
        assert "核心结论" not in summary  # assistant verdict 不进摘要（防编造传染）


# ============================================================
# 单元测试 4：prompt 缓存友好布局（不调LLM）
# ============================================================

class TestPromptCachingLayout:
    """验证重排后的缓存友好布局：静态规则前置、动态内容统一收尾

    DashScope 隐式缓存按最长公共前缀匹配（门槛约256 token），
    公共前缀越长命中收益越大；本测试固化"静态前缀稳定、动态内容集中在尾部"。
    """

    @staticmethod
    def _common_prefix_len(a: str, b: str) -> int:
        n = min(len(a), len(b))
        i = 0
        while i < n and a[i] == b[i]:
            i += 1
        return i

    def test_static_prefix_stable(self):
        """不同命盘/历史/风格构建的 prompt，静态公共前缀 ≥ 5000 字"""
        ctx2 = dict(FIXED_CONTEXT, user_question="完全不同的问题：感情运势如何？")
        opening_a = ("痛点直击式", OPENING_STYLES["痛点直击式"])
        opening_b = ("现状承接式", OPENING_STYLES["现状承接式"])
        summary_a = ("时间轴", SUMMARY_STYLES["时间轴"])
        summary_b = ("行动清单", SUMMARY_STYLES["行动清单"])
        p1 = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY, opening_a, summary_a)
        p2 = _build_prompt(ctx2, "", opening_b, summary_b)
        prefix_len = self._common_prefix_len(p1, p2)
        assert prefix_len >= 5000, f"静态公共前缀仅{prefix_len}字，缓存收益受限"

    def test_dynamic_section_order(self):
        """动态内容统一收尾：对照示例 → 本次会话信息（命盘→历史→风格→问题）"""
        opening = ("痛点直击式", OPENING_STYLES["痛点直击式"])
        summary = ("时间轴", SUMMARY_STYLES["时间轴"])
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY, opening, summary)
        # 静态区在前，动态区在后
        assert prompt.rindex("## 对照示例") < prompt.index("# 本次会话信息")
        session_pos = prompt.index("# 本次会话信息")
        # 动态区内顺序：命盘 → 历史 → 风格 → 问题
        assert prompt.index("## 命盘数据", session_pos) < prompt.index("## 此前对话话题", session_pos)
        assert prompt.index("## 此前对话话题", session_pos) < prompt.index("## 本轮风格要求", session_pos)
        assert prompt.index("## 本轮风格要求", session_pos) < prompt.index("## 用户问题", session_pos)
        # 本轮风格区块包含选中风格名
        style_section = prompt[prompt.index("## 本轮风格要求"):]
        assert "痛点直击式" in style_section
        assert "时间轴" in style_section

    def test_anchor_phrases_intact(self):
        """重排后探针字典与既有测试依赖的锚点短语全部保留"""
        prompt = _build_prompt(FIXED_CONTEXT, WRONG_HISTORY)
        # 来源：_rule_checks / _consistency_checks / _verdict_consistency_checks 探针
        # 及 TestPromptConsistencyRules 既有断言
        anchors = [
            "命盘数据是最高推演依据",
            "以命盘为准",
            "不盲从惯性判断",
            "严禁编造命理依据",
            "未来剧本",
            "closing 硬约束",
            "逐点对应",
            "守得住基本盘",
            "禁止closing复述",
            "错误写法5",
            "此前对话话题",
            "opening.verdict 必须从 subtopic 的实际细节中提炼",
            "写完全部 subtopic 后强制回查",
            "模糊预判术语必须定义边界",
            "通用高频模糊词二分定义",
            "三段闭环",
            "禁止用节气当行动节点",
            "单个 narrative 内部必须逻辑自洽",
            "关键词/标题必须正面回答用户问题",
            "结论与建议必须因果衔接",
            "输出前自检",
            "全报告统一适用",
            "没有任何历史结论",
        ]
        for phrase in anchors:
            assert phrase in prompt, f"锚点短语丢失：{phrase}"


# ============================================================
# 集成测试：LLM 不被错误历史摘要带偏（调真实 API）
# ============================================================

_API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
_API_URL = os.getenv("AI_BASE_URL", "https://ws-ekdxihtd67l14sw6.cn-beijing.maas.aliyuncs.com/compatible-mode/v1") + "/chat/completions"
_LLM_MODEL = os.getenv("AI_MODEL", "qwen-plus-latest")

pytestmark_integration = pytest.mark.skipif(
    not _API_KEY,
    reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 集成测试",
)


@pytest.mark.skipif(not _API_KEY, reason="未配置 DASHSCOPE_API_KEY，跳过 LLM 集成测试")
class TestLLMNotContaminated:
    """集成测试：注入错误历史摘要，验证 LLM 仍以命盘为准

    命盘事实：壬水弱 + 2027丁未火土忌神 = 不利创业
    错误历史：2027适合创业扩张
    期望：LLM 不盲从错误历史，输出"不宜/守/慎"等以命盘为准的结论
    """

    def _call_llm(self, history_summary: str) -> dict:
        """用 build_structured_prompt 构造 prompt 并调用 LLM，返回解析后的 dict"""
        prompt = _build_prompt(FIXED_CONTEXT, history_summary)
        body = json.dumps({
            "model": _LLM_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": FIXED_CONTEXT["user_question"]},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 4000,
        }).encode()
        req = urllib.request.Request(
            _API_URL, data=body,
            headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
        content = resp["choices"][0]["message"]["content"]
        # 复用生产容错：先直接解析，失败则用 _extract_and_fix_json 修复（处理裸换行/markdown包裹等）
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            fixed = _extract_and_fix_json(content)
            result = json.loads(fixed)
        # 打印 verdict 便于人工核对（pytest -s 可见）
        _v = result.get("opening", {}).get("verdict", "")
        print(f"\n[verdict] {_v[:300]}")
        return result

    def test_wrong_history_not_followed(self):
        """错误历史(适合创业)下，LLM 应以命盘为准(不宜)，不盲从"""
        data = self._call_llm(WRONG_HISTORY)
        verdict = data.get("opening", {}).get("verdict", "")

        # 反向信号：明确盲从错误历史，禁止出现（用正向推荐短语，避免"不适合创业"否定句误匹配）
        blind_signals = ["建议创业", "该创业", "可以创业", "创业扩张", "创业最稳", "创业好时机", "创业吉", "创业旺", "创业爆", "事业爆发期"]
        for w in blind_signals:
            assert w not in verdict, f"被错误历史带偏(含'{w}'): verdict={verdict}"

        # 正向信号：以命盘为准，至少一个（覆盖 LLM 多样化表述）
        bazi_signals = ["不宜", "不适合", "避开", "慎", "暂缓", "推迟", "压后", "得等", "2028",
                        "守住", "稳住", "火土旺", "水气弱", "架在火上", "耗身", "破财", "忌神"]
        assert any(w in verdict for w in bazi_signals), f"未以命盘为准(无命盘信号): verdict={verdict}"

    def test_right_history_kept(self):
        """正确历史(不宜)下，LLM 结论与命盘一致"""
        data = self._call_llm(RIGHT_HISTORY)
        verdict = data.get("opening", {}).get("verdict", "")
        bazi_signals = ["不宜", "不适合", "避开", "慎", "暂缓", "推迟", "压后", "得等", "2028",
                        "守住", "稳住", "火土旺", "水气弱", "架在火上", "耗身", "破财", "忌神"]
        assert any(w in verdict for w in bazi_signals), f"正确历史下结论偏离命盘: verdict={verdict}"

    def test_no_fabricated_bazi_basis(self):
        """narrative 不编造 prompt 未提供的命理依据

        prompt 只给了 current_dayun=丙午(火土忌神)，若 LLM 说"大运助金水"
        就是编造反命盘依据来迎合错误历史，必须禁止。
        """
        data = self._call_llm(WRONG_HISTORY)
        all_text = json.dumps(data, ensure_ascii=False)
        # 典型编造模式：大运助金水/大运生身（实际丙午是忌神运，不可能助身）
        assert "大运助金水" not in all_text, f"编造'大运助金水': {all_text[:300]}"
        assert "大运生身" not in all_text, f"编造'大运生身': {all_text[:300]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
